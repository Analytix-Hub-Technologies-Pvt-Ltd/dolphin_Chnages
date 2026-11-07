# pipeline/retrieval.py

import re
import json
from typing import Any, Dict, List, Optional
from loguru import logger

from config import settings
from models.database import get_pool
from retrieval.faiss_store import DEFAULT_TOP_K
from retrieval.postgres_loader import PostgresLoader


# -----------------------------
# SAFE GET
# -----------------------------
def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


# -----------------------------
# NORMALIZE VIDEO URL
# -----------------------------
def normalize_video_url(url: str) -> str:
    if not url:
        return ""

    url = url.strip().lower()

    if url.startswith("http://"):
        url = url.replace("http://", "https://", 1)

    if "?" in url:
        base, query = url.split("?", 1)
        important = []
        for p in query.split("&"):
            if p.split("=")[0] in ["v", "id", "video_id"]:
                important.append(p)
        url = base + ("?" + "&".join(important) if important else "")

    return url.rstrip("/")


# -----------------------------
# MEDIA PARSER
# -----------------------------
def coerce_media(value):
    if value is None:
        return []

    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]

    if isinstance(value, dict):
        return [value]

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except:
            return []

    return []


# -----------------------------
# NORMALIZE CHUNK
# -----------------------------
def normalize_chunk(raw):
    topic = raw.get("topic_name", "") or raw.get("title", "")
    content = raw.get("topic_content", "") or raw.get("content", "")
    topic_code = raw.get("topic_code", "")

    videos = coerce_media(raw.get("topic_video") or raw.get("videos"))
    images = coerce_media(raw.get("topic_image") or raw.get("images"))
    if not images and topic_code:
        try:
            from services.image_service import ImageService
            img_service = ImageService()
            images = img_service.get_images_by_topic_code(topic_code)
        except Exception:
            pass
    pdfs = coerce_media(raw.get("topic_pdf") or raw.get("pdfs"))

    full_content = f"{topic}\n\n{content}" if topic and not content.startswith(topic) else content

    return {
        "content_id": raw.get("content_id"),
        "topic_name": topic,
        "topic_code": topic_code,
        "topic_content": content,
        "content": full_content,
        "videos": videos,
        "images": images,
        "pdfs": pdfs,
        "_score": raw.get("_score"),
        "_rank": raw.get("_rank"),
    }


# -----------------------------
# VIDEO EXTRACTION
# -----------------------------
def extract_videos(chunks, existing_videos, max_videos=15):
    seen = set()
    result = []

    for c in chunks:
        for v in c.get("videos", []):
            url = normalize_video_url(v.get("url") or v.get("videourl") or "")
            if not url or url in seen:
                continue
            seen.add(url)
            result.append(v)

    result.extend(existing_videos)

    return result[:max_videos]



# -----------------------------
# MAIN FUNCTION
# -----------------------------
async def retrieval_node(
    state: Dict[str, Any],
    vector_store,
    query_expansion_service=None,
) -> Dict[str, Any]:

    user_profile = (
            safe_get(state, "user_profile") or
            safe_get(state, "user") or   # fallback support
            {}
        )

    query = safe_get(state, "current_query", "") or ""
    decision = safe_get(state, "router_decision", {}) or {}
    company_id = user_profile.get("company_id")
    node_type = decision.get("node_type", "query")

    existing_chunks = safe_get(state, "retrieval_chunks", []) or []
    existing_videos = safe_get(state, "video_suggestions", []) or []

    standalone_query = decision.get("standalone_query") or query

    # -----------------------------
    # ⚡ SKIP DUPLICATE RETRIEVAL (Ensure SME memory is checked)
    # -----------------------------
    if existing_chunks and node_type != "quiz":
        logger.info("⚡ Reusing existing chunks")
        has_sme = any(c.get("_is_sme_approved") for c in existing_chunks)
        if not has_sme and not state.get("_sme_checked"):
            try:
                from api.dependencies import get_approved_memory_service
                approved_service = await get_approved_memory_service()
                approved_mem = await approved_service.search_approved_memory(
                    standalone_query or query,
                    company_id=company_id,
                )
                if approved_mem and approved_mem.get("preferred_response"):
                    sme_pref = approved_mem["preferred_response"]
                    is_direct = approved_mem.get("is_direct_override", True)
                    logger.info(
                        f"🌟 Retrieved SME-Approved match (direct={is_direct}, score={approved_mem.get('score', 1.0):.2f}) "
                        f"for query '{(standalone_query or query)[:50]}'"
                    )
                    sme_chunk = {
                        "content_id": 999999,
                        "topic_code": "SME-OFFICIAL-GUIDANCE",
                        "topic_name": "SME Approved Guidance",
                        "topic_content": sme_pref,
                        "content": f"SME Approved Guidance\n\n[OFFICIAL SME-VERIFIED GUIDANCE - HIGH PRIORITY OVERRIDE]:\n{sme_pref}",
                        "videos": [],
                        "images": [],
                        "pdfs": [],
                        "_score": float(approved_mem.get("score", 1.0)),
                        "_rank": 0,
                        "_is_sme_approved": True,
                        "_is_direct_override": is_direct,
                        "_sme_preferred_response": sme_pref,
                        "_sme_feedback_id": approved_mem.get("feedback_id"),
                        "_sme_match_type": approved_mem.get("match_type", "exact"),
                    }
                    existing_chunks.insert(0, sme_chunk)
            except Exception as mem_err:
                logger.warning(f"Approved memory search error on existing chunks: {mem_err}")

        state["retrieval_chunks"] = existing_chunks
        state["video_suggestions"] = extract_videos(existing_chunks, existing_videos)
        return state

    search_query = standalone_query
    raw_user_query = standalone_query

    # -----------------------------
    # CARRIER FRAME DISENTANGLEMENT
    # -----------------------------
    # Detect administrative preamble wrappers (e.g., "PSC inspection checklist for <Core Subject>")
    # Emphasize the core technical question so container words don't hijack the search results.
    prefix_patterns = [
        r'^(?:port\s+state\s+control\s+(?:psc\s+)?inspection\s+checklist\s+for\s+)(.*)$',
        r'^(?:auditor\s+checklist\s+(?:and\s+penalties\s+)?(?:for\s+non-compliance\s+with\s+|for\s+)?)(.*)$',
        r'^(?:summary\s+of\s+changes\s+effective\s+dates\s+(?:and\s+grandfather\s+clauses\s+)?for\s+)(.*)$',
        r'^(?:how\s+to\s+prepare\s+vessel\s+survey\s+and\s+certificate\s+endorsements\s+for\s+)(.*)$',
        r'^(?:imo\s+circulars?\s+and\s+resolution\s+implementation\s+dates\s+for\s+)(.*)$',
        r'^(?:flag\s+state\s+enforcement\s+(?:and\s+survey\s+deadlines\s+)?regarding\s+)(.*)$',
        r'^(?:troubleshooting\s+and\s+safety\s+guidelines\s+for\s+)(.*)$',
        r'^(?:chief\s+engineer\s+checklist\s+for\s+)(.*)$',
        r'^(?:detailed\s+regulatory\s+guidance\s*:\s*)(.*)$',
    ]
    for pat in prefix_patterns:
        m = re.match(pat, search_query, re.IGNORECASE)
        if m:
            extracted_core = m.group(1).strip()
            if len(extracted_core) >= 8:
                search_query = f"{extracted_core} {search_query}"
            break

    # -----------------------------
    # ACRONYM DOMAIN EXPANSION
    # -----------------------------
    try:
        from services.maritime_acronyms import find_acronyms_in_query, get_acronym_expansion
        acrs = find_acronyms_in_query(search_query)
        if not acrs:
            # Check for unknown uppercase acronym candidates (2 to 6 chars) and resolve JIT
            candidate_tokens = re.findall(r'\b[A-Z0-9]{2,6}\b', search_query)
            if not candidate_tokens and len(search_query.split()) <= 4:
                from services.dynamic_acronym_service import COMMON_NON_ACRONYMS
                raw_tokens = [w.strip().upper() for w in re.findall(r'\b[a-zA-Z0-9]{2,6}\b', search_query)]
                candidate_tokens = [t for t in raw_tokens if t not in COMMON_NON_ACRONYMS]
            if candidate_tokens:
                from services.dynamic_acronym_service import dynamic_acronym_service
                for cand in candidate_tokens:
                    resolved = await dynamic_acronym_service.resolve_acronym(cand)
                    if resolved:
                        acrs.append(cand)
        for acr in acrs:
            exps = get_acronym_expansion(acr)
            if exps:
                search_query += " " + " ".join(exps[:3])
    except Exception:
        pass

    # -----------------------------
    # QUERY EXPANSION
    # -----------------------------
    if query_expansion_service:
        try:
            search_query = await query_expansion_service.expand_query(
                search_query,
                chat_history=safe_get(state, "messages", []),
                use_llm=settings.query_expansion_use_llm,
            )
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")

    # -----------------------------
    # VECTOR SEARCH
    # -----------------------------
    try:
        # Fetch wider pool (2× K) so the downstream relevance filter and reranking
        # steps see more candidates. Correct chunk at rank-11 was previously invisible.
        chunks = await vector_store.search_with_embeddings(
            search_query,
            k=DEFAULT_TOP_K * 2,    # fetch 20 internally; trimmed after normalization
            original_query=raw_user_query,
        )
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        chunks = []

    # -----------------------------
    # DB FETCH
    # -----------------------------
    content_ids = [c.get("content_id") for c in chunks if c.get("content_id")]

    db_rows = {}
    if content_ids:
        try:
            pool = await get_pool()
            loader = PostgresLoader(pool)
            db_rows = await loader.fetch_course_content_by_ids(content_ids)
        except Exception as e:
            logger.error(f"DB fetch failed: {e}")

    # -----------------------------
    # NORMALIZE & RELEVANCE FILTER
    # -------------------------
    normalized = []
    for c in chunks:
        db = db_rows.get(c.get("content_id"))
        merged = {**c, **(db or {})}

        # Zero-hallucination relevance filter: drop chunks with very high distance and no BM25 match
        score = merged.get("_score")
        has_bm25 = merged.get("_bm25_score") is not None and merged.get("_bm25_score", 0) > 0
        has_topic_match = merged.get("_has_topic_match", False)

        if score is not None:
            try:
                # Adaptive relevance threshold: long/complex queries produce higher L2 distances
                # naturally because the query embedding blends many concepts.
                # Short query (1–3 words):  threshold ≈ 1.45 (same as before, no change)
                # Medium query (5–6 words): threshold ≈ 1.60
                # Long query  (8+ words):   threshold = 1.75 (lenient for complex questions)
                _query_words = len((search_query or "").split())
                _length_factor = min(1.0, _query_words / 8.0)
                _effective_threshold = 1.45 + (0.30 * _length_factor)

                if not has_bm25 and not has_topic_match and float(score) > _effective_threshold:
                    logger.info(
                        f"Dropping low-relevance chunk in retrieval_node: topic='{merged.get('topic_name')}', "
                        f"score={score:.4f} threshold={_effective_threshold:.2f} query_words={_query_words}"
                    )
                    continue
            except (TypeError, ValueError):
                pass

        # Drop single-letter or noise topic chunks (e.g. 'N', 'F', '1.') when query has real technical content
        t_name = (merged.get("topic_name") or merged.get("title") or "").strip()
        if len(t_name) <= 2 and len(search_query.strip()) > 2:
            logger.info(f"Dropping single-character noise chunk in retrieval_node: topic='{t_name}'")
            continue

        # Maritime Acronym Conflict Filter: drop chunks whose topic has a conflicting maritime acronym
        from services.maritime_acronyms import has_conflicting_acronym
        if has_conflicting_acronym(search_query, t_name):
            logger.info(
                f"Dropping chunk with conflicting acronym in retrieval_node: topic='{t_name}' vs query='{search_query}'"
            )
            continue

        normalized.append(normalize_chunk(merged))

    if not normalized and chunks:
        from services.off_topic_detector import is_marine_domain_query, is_obvious_marine_query
        from services.maritime_acronyms import find_acronyms_in_query
        if is_marine_domain_query(search_query) or is_obvious_marine_query(search_query) or bool(find_acronyms_in_query(search_query)):
            logger.info("⚠️ Filter dropped all chunks in retrieval_node; retaining top raw chunks as safety fallback for marine query")
            for c in chunks[:2]:
                db = db_rows.get(c.get("content_id"))
                normalized.append(normalize_chunk({**c, **(db or {})}))
        else:
            logger.info(f"🚫 Dropped low-relevance chunks for non-marine query in retrieval_node: '{search_query[:50]}'")

    final_chunks = list(normalized or existing_chunks)

    # Content-aware temporal & regulatory re-ranking
    q_lower_reg = search_query.lower()
    temporal_regulatory_matches = re.findall(
        r'\b(20[1-3]\d|jan(?:uary)?|effective|amendment|amendments|regulation|regulations|rule|rules|mepc(?:\.\d+)?|seemp|force|dcs|eu\s*ets|fueleu|ets)\b',
        q_lower_reg
    )
    if temporal_regulatory_matches and len(final_chunks) > 1:
        query_constraints = set(temporal_regulatory_matches)
        has_year = any(re.match(r'^(20[1-3]\d)$', t) for t in query_constraints)
        has_eu_ets = any(t in ("eu ets", "eu", "ets", "fueleu") for t in query_constraints)

        def _constraint_score(c):
            t_name_lower = str(c.get('topic_name', '')).lower()
            full_text = f"{t_name_lower} {str(c.get('topic_content', ''))[:4000]}".lower()
            matches = sum(1 for term in query_constraints if re.search(r'\b' + re.escape(term) + r'\b', full_text))
            year_match = 3 if has_year and any(re.search(r'\b' + re.escape(y) + r'\b', full_text) for y in query_constraints if re.match(r'^(20[1-3]\d)$', y)) else 0
            eu_boost = 3 if has_eu_ets and ("eu regulation" in t_name_lower or "regional" in t_name_lower or "ets" in t_name_lower) else 0
            return matches + year_match + eu_boost

        max_matches = max(_constraint_score(c) for c in final_chunks)
        if max_matches >= 2:
            final_chunks.sort(key=lambda c: _constraint_score(c), reverse=True)
            if has_year and any(_constraint_score(c) >= 3 for c in final_chunks):
                matched_chunks = [c for c in final_chunks if _constraint_score(c) > 0]
                if matched_chunks:
                    final_chunks = matched_chunks
            for r_idx, c in enumerate(final_chunks):
                c["_rank"] = r_idx
            logger.info(f"⚡ [Temporal/Regulatory Rerank] Boosted chunks matching {query_constraints} in retrieval_node to rank 0 (count={len(final_chunks)})")

    # -----------------------------
    # BROAD OVERVIEW & ACRONYM RE-RANKING
    # -----------------------------
    # When user asks a standalone abbreviation (e.g. "EGCS", "ECDIS", "OWS") or full name
    # without specific procedural constraints, boost the foundational Introduction/Overview chunk to rank 0.
    if len(final_chunks) > 1 and not temporal_regulatory_matches:
        from services.maritime_acronyms import find_acronyms_in_query
        q_raw = (standalone_query or query or "").strip()
        q_clean = re.sub(r'[^\w\s]', '', q_raw).strip()
        words = q_clean.split()

        procedural_keywords = {
            "calibrate", "calibration", "sensor", "sensors", "test", "testing",
            "alarm", "alarms", "limit", "limits", "threshold", "thresholds",
            "troubleshoot", "troubleshooting", "maintenance", "procedure", "procedures",
            "overboard", "washwater", "ph", "filter", "filters", "pump", "pumps",
            "step", "steps", "action", "actions", "checklist", "checklists"
        }
        has_procedural_constraint = any(w.lower() in procedural_keywords for w in words)

        is_broad = False
        query_acrs = find_acronyms_in_query(q_raw)
        if query_acrs and len(words) <= 5 and not has_procedural_constraint:
            is_broad = True
        elif len(words) <= 4 and not has_procedural_constraint:
            is_broad = True
        elif re.match(r'^(?:what\s+is|what\s+are|explain|overview\s+of|intro(?:duction)?\s+to)\b', q_raw, re.IGNORECASE) and not has_procedural_constraint:
            is_broad = True

        if is_broad:
            intro_pats = [
                re.compile(r'^(?:what\s+is|overview\s+of|introduction\s+to|about|general\s+principles\s+of)\b', re.IGNORECASE),
                re.compile(r'\b(?:overview|introduction|fundamentals|basics)\b', re.IGNORECASE),
            ]

            def _intro_score(c):
                t_name = str(c.get("topic_name") or c.get("title") or "").strip()
                t_name_lower = t_name.lower()
                score = 0
                if intro_pats[0].search(t_name):
                    score += 10
                elif intro_pats[1].search(t_name):
                    score += 5

                # Boost if topic name directly matches the acronym or full term
                if query_acrs:
                    for acr in query_acrs:
                        if re.search(rf'\b{re.escape(acr.lower())}\b', t_name_lower):
                            score += 4
                elif q_clean.lower() in t_name_lower:
                    score += 4

                # Penalize specific subtopic keywords if looking for foundational overview
                if any(w in t_name_lower for w in ["calibration", "maintenance", "troubleshooting", "alarm", "scheme", "sensor", "washwater"]):
                    score -= 3
                return score

            best_idx = -1
            best_score = 0
            for idx, c in enumerate(final_chunks):
                s = _intro_score(c)
                if s > best_score:
                    best_score = s
                    best_idx = idx

            if best_idx > 0 and best_score >= 4:
                intro_chunk = final_chunks.pop(best_idx)
                final_chunks.insert(0, intro_chunk)
                for r_idx, c in enumerate(final_chunks):
                    c["_rank"] = r_idx
                logger.info(f"⚡ [Broad Overview Rerank] Boosted introductory chunk '{intro_chunk.get('topic_name')}' to rank 0 for query '{q_raw}'")

    # -----------------------------
    # 🌟 IMMEDIATE APPROVED FEEDBACK MEMORY CHECK
    # -----------------------------
    try:
        from api.dependencies import get_approved_memory_service
        approved_service = await get_approved_memory_service()
        approved_mem = await approved_service.search_approved_memory(
            search_query,
            company_id=company_id,
        )
        if approved_mem and approved_mem.get("preferred_response"):
            sme_pref = approved_mem["preferred_response"]
            is_direct = approved_mem.get("is_direct_override", True)
            logger.info(
                f"🌟 Retrieved SME-Approved match (direct={is_direct}, score={approved_mem.get('score', 1.0):.2f}) "
                f"for query '{search_query[:50]}'"
            )
            
            sme_chunk = {
                "content_id": 999999,
                "topic_code": "SME-OFFICIAL-GUIDANCE",
                "topic_name": "SME Approved Guidance",
                "topic_content": sme_pref,
                "content": f"SME Approved Guidance\n\n[OFFICIAL SME-VERIFIED GUIDANCE - HIGH PRIORITY OVERRIDE]:\n{sme_pref}",
                "videos": [],
                "images": [],
                "pdfs": [],
                "_score": float(approved_mem.get("score", 1.0)),
                "_rank": 0,
                "_is_sme_approved": True,
                "_is_direct_override": is_direct,
                "_sme_preferred_response": sme_pref,
                "_sme_feedback_id": approved_mem.get("feedback_id"),
                "_sme_match_type": approved_mem.get("match_type", "exact"),
            }
            final_chunks.insert(0, sme_chunk)
    except Exception as mem_err:
        logger.warning(f"Approved memory search error in retrieval_node: {mem_err}")

    company_vector_store = safe_get(
        state,
        "company_vector_store"
    )


    # -----------------------------
    # COMPANY RETRIEVAL
    # -----------------------------
    company_chunks = []

    company_vector_store = safe_get(state, "company_vector_store")

    if company_id and company_vector_store:

        logger.info(f"Searching company documents for company_id={company_id}")

        try:
            company_results = await company_vector_store.search_with_embeddings(
                search_query,
                k=5,
            )

            logger.info(
                f"Company FAISS returned {len(company_results)} chunks"
            )

            for chunk in company_results:

                if str(chunk.get("company_id")) != str(company_id):
                    continue

                company_chunks.append(
                    normalize_chunk(chunk)
                )

            logger.info(
                f"Matched company chunks: {len(company_chunks)}"
            )

        except Exception as e:
            logger.exception(f"Company retrieval failed: {e}")

    # -----------------------------
    # VIDEOS
    # -----------------------------
    videos = extract_videos(final_chunks, existing_videos)

    # -----------------------------
    # UPDATE STATE
    # -----------------------------
    state["retrieval_chunks"] = final_chunks
    state["company_chunks"] = company_chunks
    state["video_suggestions"] = videos
    state["standalone_query"] = standalone_query
    state["company_answer"] = None

    logger.info(
        f"Marine chunks : {len(final_chunks)}"
    )

    logger.info(
        f"Company chunks : {len(company_chunks)}"
    )

    return state