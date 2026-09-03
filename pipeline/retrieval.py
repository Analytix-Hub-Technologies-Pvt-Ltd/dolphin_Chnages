# pipeline/retrieval.py

import re
import json
from typing import Any, Dict, List, Optional
from loguru import logger

from config import settings
from models.database import get_pool
from retrieval.faiss_store import DEFAULT_TOP_K
from retrieval.postgres_loader import PostgresLoader
from pipeline.manual_filter import is_manual_allowed_for_ship_type


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
# NORMALIZE VIDEO OBJECT
# -----------------------------
def normalize_video_item(v: Any, default_title: str = "") -> Optional[Dict[str, Any]]:
    if not isinstance(v, dict):
        return None
    url = v.get("url") or v.get("Url") or v.get("videourl") or v.get("VideoUrl") or ""
    if not url:
        return None
    thumbnail = v.get("thumbnail") or v.get("Thumbnail") or v.get("thumbnail_url") or v.get("ThumbnailUrl") or ""
    title = v.get("title") or v.get("Title") or default_title or "Video"
    about = v.get("about") or v.get("About") or ""
    vid_id = v.get("id") or v.get("Id") or ""

    return {
        "id": vid_id,
        "Id": vid_id,
        "url": url,
        "Url": url,
        "thumbnail": thumbnail,
        "Thumbnail": thumbnail,
        "title": title,
        "Title": title,
        "about": about,
        "About": about,
    }


# -----------------------------
# NORMALIZE CHUNK
# -----------------------------
def normalize_chunk(raw):
    topic = raw.get("topic_name", "")
    content = raw.get("topic_content", "") or raw.get("content", "")

    raw_videos = coerce_media(raw.get("videos") or raw.get("topic_video"))
    raw_images = coerce_media(raw.get("images") or raw.get("topic_image"))
    raw_pdfs = coerce_media(raw.get("pdfs") or raw.get("topic_pdf"))

    videos = [
        norm for v in raw_videos
        if (norm := normalize_video_item(v, default_title=topic)) is not None
    ]

    return {
        "content_id": raw.get("content_id"),
        "topic_name": topic,
        "content": f"{topic}\n\n{content}" if content else topic,
        "videos": videos,
        "images": raw_images,
        "pdfs": raw_pdfs,
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
            normalized_v = normalize_video_item(v, default_title=c.get("topic_name", ""))
            if not normalized_v:
                continue
            url = normalize_video_url(normalized_v.get("url", ""))
            if not url or url in seen:
                continue
            seen.add(url)
            result.append(normalized_v)

    for v in existing_videos:
        normalized_v = normalize_video_item(v) if isinstance(v, dict) else None
        if not normalized_v:
            continue
        url = normalize_video_url(normalized_v.get("url", ""))
        if url and url not in seen:
            seen.add(url)
            result.append(normalized_v)

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
    # ⚡ SKIP DUPLICATE RETRIEVAL
    # -----------------------------
    if existing_chunks and node_type != "quiz":
        logger.info("⚡ Reusing existing chunks")

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
    # NORMALIZE
    # -----------------------------
    normalized = []
    for c in chunks:
        db = db_rows.get(c.get("content_id"))
        merged = {**c, **(db or {})}
        normalized.append(normalize_chunk(merged))

    final_chunks = normalized or existing_chunks

    company_vector_store = safe_get(
        state,
        "company_vector_store"
    )

    # -----------------------------
    # COMPANY RETRIEVAL
    # -----------------------------
    existing_company_chunks = state.get("company_chunks", []) or []
    company_chunks = list(existing_company_chunks)

    if company_id and company_vector_store and not company_chunks:
        from pipeline.company_retrieval import is_company_match

        ship_type = user_profile.get("ship_type") or user_profile.get("ShipType") or ""
        company_name = (
            user_profile.get("company_name")
            or user_profile.get("CompanyName")
            or user_profile.get("company")
            or ""
        )
        logger.info(f"Searching company documents for company_id={company_id}, ship_type={ship_type}")

        try:
            company_results = await company_vector_store.search_with_embeddings(
                search_query,
                k=40,
            )

            logger.info(
                f"Company FAISS returned {len(company_results)} chunks"
            )

            for chunk in company_results:
                chunk_company_id = chunk.get("company_id")
                chunk_cname = chunk.get("company_name", "")
                if not is_company_match(chunk_company_id, company_id, company_name, chunk_cname):
                    continue

                doc_title = chunk.get("document_title", "")
                if not is_manual_allowed_for_ship_type(doc_title, ship_type):
                    logger.info(f"Filtered out chunk ('{doc_title}') for ship type '{ship_type}'")
                    continue

                company_chunks.append(
                    normalize_chunk(chunk)
                )
                if len(company_chunks) >= 20:
                    break

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