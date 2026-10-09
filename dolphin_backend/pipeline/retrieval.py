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
                    logger.info(f"🌟 Retrieved SME-Approved Override for query '{(standalone_query or query)[:50]}'")
                    sme_chunk = {
                        "content_id": 999999,
                        "topic_code": "SME-OFFICIAL-GUIDANCE",
                        "topic_name": "SME Approved Guidance",
                        "topic_content": sme_pref,
                        "content": f"SME Approved Guidance\n\n[OFFICIAL SME-VERIFIED GUIDANCE - HIGH PRIORITY OVERRIDE]:\n{sme_pref}",
                        "videos": [],
                        "images": [],
                        "pdfs": [],
                        "_score": 1.0,
                        "_rank": 0,
                        "_is_sme_approved": True,
                        "_sme_preferred_response": sme_pref,
                        "_sme_feedback_id": approved_mem.get("feedback_id"),
                    }
                    existing_chunks.insert(0, sme_chunk)
            except Exception as mem_err:
                logger.warning(f"Approved memory search error on existing chunks: {mem_err}")

        state["retrieval_chunks"] = existing_chunks
        state["video_suggestions"] = extract_videos(existing_chunks, existing_videos)
        return state

    search_query = standalone_query

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
        chunks = await vector_store.search_with_embeddings(
            search_query,
            k=DEFAULT_TOP_K
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
                if not has_bm25 and not has_topic_match and float(score) > 1.45:
                    logger.info(
                        f"Dropping low-relevance chunk in retrieval_node: topic='{merged.get('topic_name')}', score={score}"
                    )
                    continue
            except (TypeError, ValueError):
                pass

        # Maritime Acronym Conflict Filter: drop chunks whose topic has a conflicting maritime acronym
        from services.maritime_acronyms import has_conflicting_acronym
        t_name = merged.get("topic_name") or merged.get("title") or ""
        if has_conflicting_acronym(search_query, t_name):
            logger.info(
                f"Dropping chunk with conflicting acronym in retrieval_node: topic='{t_name}' vs query='{search_query}'"
            )
            continue

        normalized.append(normalize_chunk(merged))

    if not normalized and chunks:
        logger.info("⚠️ Filter dropped all chunks in retrieval_node; retaining top raw chunks as safety fallback")
        for c in chunks[:2]:
            db = db_rows.get(c.get("content_id"))
            normalized.append(normalize_chunk({**c, **(db or {})}))

    final_chunks = list(normalized or existing_chunks)

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
            logger.info(f"🌟 Retrieved SME-Approved Override for query '{search_query[:50]}'")
            
            sme_chunk = {
                "content_id": 999999,
                "topic_code": "SME-OFFICIAL-GUIDANCE",
                "topic_name": "SME Approved Guidance",
                "topic_content": sme_pref,
                "content": f"SME Approved Guidance\n\n[OFFICIAL SME-VERIFIED GUIDANCE - HIGH PRIORITY OVERRIDE]:\n{sme_pref}",
                "videos": [],
                "images": [],
                "pdfs": [],
                "_score": 1.0,
                "_rank": 0,
                "_is_sme_approved": True,
                "_sme_preferred_response": sme_pref,
                "_sme_feedback_id": approved_mem.get("feedback_id"),
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