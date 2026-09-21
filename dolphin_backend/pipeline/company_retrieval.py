import asyncio
import hashlib
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger
from pipeline.manual_filter import is_manual_allowed_for_ship_type
from retrieval.normalization import (
    extract_distinctive_terms,
    normalize_text_for_retrieval,
    simple_stem,
    tokenize_for_retrieval,
    is_term_or_compound_in_text,
)
from retrieval.precision_scorer import compute_chunk_precision_score


def get_doc_priority(doc_title: str, doc_type: str = "") -> int:
    """
    Determine priority of document type:
    0: Primary Shipboard SMS Manuals
    1: Company Policies and SOPs
    2: Checklists, Forms, and Permits
    3: Other auxiliary documents
    """
    title_lower = (doc_title or "").lower()
    type_lower = (doc_type or "").lower()
    if "sms manual" in title_lower or "manual" in title_lower or "sms" in type_lower:
        return 0
    if "policy" in title_lower or "procedure" in title_lower or "policy" in type_lower or "procedure" in type_lower:
        return 1
    if "form" in title_lower or "permit" in title_lower or "checklist" in title_lower or "form" in type_lower or "permit" in type_lower:
        return 2
    return 3


def is_section_header_start(text: str) -> bool:
    """
    Detect if a chunk starts with a major section header, SOP name, or chapter.
    """
    if not text:
        return False
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    if not lines:
        return False

    first_line = lines[0]

    # Check common maritime SMS numbering and section formats
    if re.match(
        r"^(?:Section\s+|SOP\s+Name:?|[I|V|X\d]+\.|\d+\.\d+|Chapter\s+|Part\s+|Form:\s+|Emergency\s+Procedure|Procedure\s*:|Policy\s*:|Guidelines?\s*:)",
        first_line,
        re.I,
    ):
        return True

    # Check for markdown headers
    if re.match(r"^#{1,3}\s+", first_line):
        return True

    # Check for docx table of contents or header blocks
    if first_line.startswith("|") and any(
        kw in first_line.lower() for kw in ["section", "description", "sms manual", "procedure", "sop"]
    ):
        return True

    # Check second line if first line is a generic doc banner
    if len(lines) > 1 and "sms manual" in first_line.lower():
        second_line = lines[1]
        if re.match(
            r"^(?:Section\s+|SOP\s+Name:?|[I|V|X\d]+\.|\d+\.\d+|Chapter\s+|Part\s+|Form:\s+|Emergency\s+Procedure|Procedure\s*:|Policy\s*:|Guidelines?\s*:)",
            second_line,
            re.I,
        ):
            return True

    return False


def is_major_section_boundary(text: str) -> bool:
    """
    Detect if a chunk marks the beginning of a NEW distinct section, SOP, or Form,
    used to terminate forward expansion so unrelated procedures are not merged.
    """
    if not text:
        return False
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    if not lines:
        return False

    first_line = lines[0]

    # Major numbered section, distinct SOP Name or Form introduction
    if re.match(r"^(?:Section\s+[IVX\d]+|SOP\s+Name:|[I|V|X\d]+\.\d+\s+[A-Z]|Form:\s+[A-Z]{2}\s*\d{3}|Chapter\s+\d+|Part\s+[IVX\d]+)", first_line, re.I):
        return True

    if first_line.startswith("|") and "table of contents" in first_line.lower():
        return True

    return False


def is_company_match(chunk_cid: Any, user_cid: Any, company_name: str = "", chunk_cname: str = "") -> bool:
    """
    Check if a chunk belongs to the user's company dynamically.
    Matches by exact ID, company name, or dynamic multi-tenant ID relationship across systems.
    """
    c_chunk = str(chunk_cid).strip() if chunk_cid is not None else ""
    c_user = str(user_cid).strip() if user_cid is not None else ""
    c_name = str(company_name).lower().strip() if company_name else ""
    c_chunk_name = str(chunk_cname).lower().strip() if chunk_cname else ""

    # 1. Direct ID match
    if c_chunk and c_user and c_chunk == c_user:
        return True

    # 2. Company name match
    if c_name and c_chunk_name and (c_name == c_chunk_name or c_name in c_chunk_name or c_chunk_name in c_name):
        return True

    # 3. Dynamic numeric/prefix relationship across multi-tenant identifier formats (e.g. user '8' with doc '824866')
    if c_chunk and c_user and (c_chunk.startswith(c_user) or c_user.startswith(c_chunk)):
        return True

    # 4. If chunk_cid matches user's company name string directly
    if c_chunk and c_name and c_chunk.lower() == c_name:
        return True

    return False


def _compute_chunk_content_hash(text: str) -> str:
    """Compute a normalized SHA-256 hash for deduplication."""
    norm = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


async def company_retrieval_node(
    state: dict,
    company_vector_store,
) -> dict:
    """
    Retrieve relevant company-specific document chunks with section-aware expansion,
    strict vessel-type and tenant filtering, gap-bridging, and priority scoring.
    """
    user_profile = state.get("user_profile", {}) or {}
    company_id = user_profile.get("company_id") or user_profile.get("CompanyId") or state.get("company_id")
    company_name = (
        user_profile.get("company_name")
        or user_profile.get("CompanyName")
        or user_profile.get("company")
        or state.get("company_name")
        or ""
    )
    ship_type = (
        user_profile.get("ship_type")
        or user_profile.get("ShipType")
        or state.get("ship_type")
        or ""
    )

    if not company_id and not company_name:
        logger.warning("No company_id or company_name found in user profile")
        state["company_chunks"] = []
        return state

    query = (
        state.get("standalone_query")
        or state.get("current_query")
    )

    if not query:
        logger.warning("No query available for company retrieval")
        state["company_chunks"] = []
        return state

    underlying_store = getattr(company_vector_store, "store", company_vector_store)

    # -------------------------------------------------------------
    # 1. Parallel Vector (FAISS) & Lexical (BM25) Retrieval
    # -------------------------------------------------------------
    t_retrieval_start = time.perf_counter()
    k_vec = 250

    async def _search_vector() -> List[Dict[str, Any]]:
        v_start = time.perf_counter()
        try:
            res = await company_vector_store.search_with_embeddings(query, k=k_vec)
            logger.info(f"[Company Retrieval] FAISS search finished in {time.perf_counter() - v_start:.3f}s (hits={len(res)})")
            return res or []
        except Exception as e:
            logger.warning(f"Company FAISS search_with_embeddings failed: {e}")
            return []

    def _search_bm25_sync() -> List[Dict[str, Any]]:
        if hasattr(company_vector_store, "search_bm25"):
            return company_vector_store.search_bm25(query, k=100) or []
        elif hasattr(underlying_store, "search_bm25"):
            return underlying_store.search_bm25(query, k=100) or []
        elif hasattr(underlying_store, "bm25_index") and underlying_store.bm25_index is not None:
            return underlying_store.bm25_index.search(query=query, top_k=100) or []
        return []

    async def _search_bm25() -> List[Dict[str, Any]]:
        b_start = time.perf_counter()
        try:
            res = await asyncio.to_thread(_search_bm25_sync)
            logger.info(f"[Company Retrieval] BM25 search finished in {time.perf_counter() - b_start:.3f}s (hits={len(res)})")
            return res or []
        except Exception as e:
            logger.warning(f"Company BM25 search failed: {e}")
            return []

    vector_task = asyncio.create_task(_search_vector())
    bm25_task = asyncio.create_task(_search_bm25())

    vector_chunks, bm25_chunks = await asyncio.gather(vector_task, bm25_task)

    # -------------------------------------------------------------
    # 3. Merge Candidates
    # -------------------------------------------------------------
    merged_candidates: Dict[Any, Dict[str, Any]] = {}
    for i, c in enumerate(vector_chunks):
        faiss_idx = c.get("_faiss_index")
        doc_id = c.get("document_id")
        chunk_idx = c.get("chunk_index")
        doc_title = c.get("document_title", "")
        content_hash = _compute_chunk_content_hash(c.get("content", ""))

        if faiss_idx is not None:
            key = ("faiss", faiss_idx)
        elif doc_id is not None and chunk_idx is not None:
            key = ("doc_chunk", doc_id, chunk_idx)
        elif doc_title and chunk_idx is not None:
            key = ("title_chunk", doc_title, chunk_idx)
        elif doc_title and content_hash:
            key = ("title_hash", doc_title, content_hash)
        else:
            key = ("vec_idx", i)

        merged_candidates[key] = dict(c)

    for i, c in enumerate(bm25_chunks):
        faiss_idx = c.get("_faiss_index")
        doc_id = c.get("document_id")
        chunk_idx = c.get("chunk_index")
        doc_title = c.get("document_title", "")
        content_hash = _compute_chunk_content_hash(c.get("content", ""))

        if faiss_idx is not None:
            key = ("faiss", faiss_idx)
        elif doc_id is not None and chunk_idx is not None:
            key = ("doc_chunk", doc_id, chunk_idx)
        elif doc_title and chunk_idx is not None:
            key = ("title_chunk", doc_title, chunk_idx)
        elif doc_title and content_hash:
            key = ("title_hash", doc_title, content_hash)
        else:
            key = ("bm25_idx", i)

        if key in merged_candidates:
            merged_candidates[key]["_bm25_score"] = c.get("_bm25_score")
        else:
            merged_candidates[key] = dict(c)

    # -------------------------------------------------------------
    # 4. Strict Company & Ship-Type Filtering
    # -------------------------------------------------------------
    valid_candidates = []
    for c in merged_candidates.values():
        chunk_company_id = c.get("company_id")
        chunk_cname = c.get("company_name", "")

        if not is_company_match(chunk_company_id, company_id, company_name, chunk_cname):
            continue

        doc_title = c.get("document_title", "")
        if not is_manual_allowed_for_ship_type(doc_title, ship_type):
            continue

        valid_candidates.append(c)

    logger.info(
        f"[Company Retrieval] Candidates - FAISS: {len(vector_chunks)}, BM25: {len(bm25_chunks)}, "
        f"Merged: {len(merged_candidates)}, Company/Ship-Type Allowed: {len(valid_candidates)}"
    )

    if not valid_candidates:
        logger.info("No valid company candidates found after company/ship-type filtering")
        state["company_chunks"] = []
        return state

    # -------------------------------------------------------------
    # 5. Precision Scoring and Distinctive Term Matching
    # -------------------------------------------------------------
    distinctive_terms = extract_distinctive_terms(query)
    max_bm25 = max([float(c.get("_bm25_score", 0.0) or 0.0) for c in valid_candidates] + [1.0])

    scored_candidates = []
    distinctive_seeds = []

    for c in valid_candidates:
        score, breakdown = compute_chunk_precision_score(
            chunk=c,
            query=query,
            standalone_query=query,
            max_bm25_in_batch=max_bm25,
        )
        c["_precision_score"] = score
        c["_precision_breakdown"] = breakdown
        scored_candidates.append((score, c))

        # Check distinctive term match in content, topic, or title
        content_lower = str(c.get("content") or c.get("topic_content") or "").lower()
        topic_lower = str(c.get("topic_name") or c.get("title") or "").lower()
        doc_lower = str(c.get("document_title") or "").lower()
        full_text = f"{topic_lower} {doc_lower} {content_lower}"

        if distinctive_terms:
            has_dist = any(
                is_term_or_compound_in_text(dt, full_text)
                for dt in distinctive_terms
            )
            if has_dist and score >= 0.8:
                distinctive_seeds.append((score, c))

    # If distinctive terms exist, only consider chunks matching them with strong precision (score >= 0.8)
    if distinctive_terms:
        if distinctive_seeds:
            seed_list = [c for score, c in sorted(distinctive_seeds, key=lambda x: x[0], reverse=True)]
        else:
            logger.info(
                f"[Company Retrieval] Query contains distinctive terms {distinctive_terms} "
                f"but NO company chunks matched with score >= 0.8. Returning empty company_chunks."
            )
            state["company_chunks"] = []
            return state
    else:
        # For generic maritime queries without distinctive terms, include valid company candidates
        qualifying_generic = [
            (score, c) for score, c in scored_candidates
            if score >= 0.4
        ]
        if not qualifying_generic:
            logger.info("[Company Retrieval] No generic company chunks qualified. Returning empty company_chunks.")
            state["company_chunks"] = []
            return state
        seed_list = [c for score, c in sorted(qualifying_generic, key=lambda x: x[0], reverse=True)]

    logger.info(
        f"[Company Retrieval] Scored seeds: {len(scored_candidates)}, Distinctive seeds: {len(distinctive_seeds)}, Qualified seed_list: {len(seed_list)}"
    )

    # -------------------------------------------------------------
    # 6. Section-Aware Context Expansion with Deep Gap Bridging
    # -------------------------------------------------------------
    all_metadata = (
        getattr(company_vector_store, "id_to_metadata", None)
        or getattr(underlying_store, "id_to_metadata", None)
        or []
    )

    doc_clusters: Dict[Tuple[str, Any], List[Dict[str, Any]]] = {}
    cluster_scores: Dict[Tuple[str, Any], float] = {}

    # Group top seeds by document
    doc_to_seeds: Dict[Tuple[str, Any], List[Dict[str, Any]]] = {}
    for seed in seed_list[:40]:
        doc_title = seed.get("document_title", "")
        doc_id = seed.get("document_id", "")
        cluster_key = (doc_title, doc_id)
        if cluster_key not in doc_to_seeds:
            doc_to_seeds[cluster_key] = []
        doc_to_seeds[cluster_key].append(seed)

    for cluster_key, seeds in doc_to_seeds.items():
        doc_title, doc_id = cluster_key
        max_score = max([s.get("_precision_score", 1.0) for s in seeds] + [1.0])
        cluster_scores[cluster_key] = max_score
        doc_clusters[cluster_key] = []

        faiss_indices = [s.get("_faiss_index") for s in seeds if s.get("_faiss_index") is not None]

        if faiss_indices and all_metadata:
            # Sort seeds by precision score descending to prioritize the most relevant sections first
            sorted_seeds = sorted(seeds, key=lambda s: s.get("_precision_score", 0.0), reverse=True)
            seen_indices = set()

            for seed in sorted_seeds[:12]:
                s_idx = seed.get("_faiss_index")
                if s_idx is None or s_idx in seen_indices:
                    continue

                # 6a. Local Backward Section Expansion (up to 10 chunks to find section header)
                b_start = s_idx
                for b in range(s_idx, max(-1, s_idx - 10), -1):
                    if 0 <= b < len(all_metadata):
                        meta = dict(all_metadata[b])
                        if (
                            meta.get("document_title") == doc_title
                            and is_company_match(meta.get("company_id"), company_id, company_name, meta.get("company_name", ""))
                            and is_manual_allowed_for_ship_type(doc_title, ship_type)
                        ):
                            b_start = b
                            if is_section_header_start(meta.get("content", "")):
                                break
                        else:
                            break

                # 6b. Local Forward Section Expansion (up to 18 chunks for full procedures & tables)
                f_end = s_idx
                for f in range(s_idx, min(len(all_metadata), s_idx + 20)):
                    if 0 <= f < len(all_metadata):
                        meta = dict(all_metadata[f])
                        if (
                            meta.get("document_title") == doc_title
                            and is_company_match(meta.get("company_id"), company_id, company_name, meta.get("company_name", ""))
                            and is_manual_allowed_for_ship_type(doc_title, ship_type)
                        ):
                            if f > s_idx and is_major_section_boundary(meta.get("content", "")):
                                break
                            f_end = f
                        else:
                            break

                # 6c. Add contiguous local section chunks
                for idx in range(b_start, f_end + 1):
                    if idx not in seen_indices and 0 <= idx < len(all_metadata):
                        seen_indices.add(idx)
                        meta = dict(all_metadata[idx])
                        if (
                            meta.get("document_title") == doc_title
                            and is_company_match(meta.get("company_id"), company_id, company_name, meta.get("company_name", ""))
                            and is_manual_allowed_for_ship_type(doc_title, ship_type)
                        ):
                            meta["_faiss_index"] = idx
                            doc_clusters[cluster_key].append(meta)
        else:
            # Fallback for mock stores or isolated index
            for s in seeds:
                doc_clusters[cluster_key].append(s)

    # -------------------------------------------------------------
    # 7. Rank Clusters by (doc_priority, -cluster_score)
    # -------------------------------------------------------------
    sorted_cluster_keys = sorted(
        doc_clusters.keys(),
        key=lambda k: (
            get_doc_priority(k[0], doc_clusters[k][0].get("doc_type", "") if doc_clusters[k] else ""),
            -cluster_scores.get(k, 0.0),
        ),
    )

    final_chunks: List[Dict[str, Any]] = []
    seen_chunk_signatures = set()

    for c_key in sorted_cluster_keys:
        cluster_chunks = doc_clusters[c_key]
        # Sort chunks within cluster strictly in natural document sequential order
        cluster_chunks.sort(
            key=lambda c: (
                c.get("chunk_index") if c.get("chunk_index") is not None else 0,
                c.get("_faiss_index") if c.get("_faiss_index") is not None else 0,
            )
        )

        for chunk in cluster_chunks:
            doc_t = chunk.get("document_title", "")
            c_idx = chunk.get("chunk_index")
            f_idx = chunk.get("_faiss_index")
            c_hash = _compute_chunk_content_hash(chunk.get("content", ""))

            sig = (doc_t, c_idx, f_idx, c_hash)
            if sig not in seen_chunk_signatures:
                seen_chunk_signatures.add(sig)
                final_chunks.append(chunk)

    # Provide generous, complete chunk capacity for the prompt
    state["company_chunks"] = final_chunks[:120]

    selected_docs = list({c.get("document_title", "Unknown") for c in state["company_chunks"]})
    logger.info(
        f"✅ Final company chunks: {len(state['company_chunks'])} across documents: {selected_docs} (total retrieval time: {time.perf_counter() - t_retrieval_start:.3f}s)"
    )

    return state
