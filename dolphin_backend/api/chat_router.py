import asyncio
import json
import re
from datetime import datetime
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from asyncpg import Pool
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from api.dependencies import (
    get_db_pool,
    get_embedding_service,
    get_faiss_store,
    get_company_store,
    get_transcribe_store,
    get_openai_service,
)
from core.rate_limiter import rate_limit_chat
from models.node_response import NodeResponse
from services.chat_service import ChatService
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService
from services.session_service import SessionService
from retrieval.faiss_store import FAISSStore
from core.redis_client import redis_service
from services.suggestion_service import SuggestionService
from models.database import get_pool
from services.query_analyzer import is_simple_social_intent, is_greeting_query

router = APIRouter(prefix="/chat", tags=["chat"])
MAX_MESSAGE_LENGTH = 4000
class ChatMessage(BaseModel):
    content: Optional[str] = None
    message: Optional[str] = None
    category: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    # Set by the UI when the user clicks a "Did you mean...?" option so the
    # (already specific) query is answered instead of being clarified again.
    skip_clarification: bool = False


class TestChatMessage(BaseModel):
    content: Optional[str] = None
    message: Optional[str] = None
    category: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    skip_clarification: bool = False

    # directly pass from frontend / login api
    name: Optional[str] = ""
    role: Optional[str] = ""
    ship: Optional[str] = ""
    ship_type: Optional[str] = ""
    company: Optional[str] = ""    

@router.post("", response_model=NodeResponse)
@rate_limit_chat
async def chat(
    request: Request,
    payload: ChatMessage,
    background_tasks: BackgroundTasks,
    pool: Pool = Depends(get_db_pool),
    openai_service: OpenAIService = Depends(get_openai_service),
    embedder: EmbeddingService = Depends(get_embedding_service),
    store: FAISSStore = Depends(get_faiss_store),
    company_store: FAISSStore = Depends(get_company_store),
    transcribe_store: FAISSStore = Depends(get_transcribe_store),
) -> NodeResponse:

    logger.info("New chat request received")

    session_service = SessionService(pool)
    chat_service = ChatService(
        openai_service,
        embedder,
        store,
        session_service,
        company_store=company_store,
        transcribe_store=transcribe_store,
    )

    user_id = payload.user_id or "anonymous"

    # SESSION
    session_id = await redis_service.get_active_session(user_id)
    logger.info(f"Redis active session: {session_id}")

    if payload.session_id:
        session_id = payload.session_id
        await redis_service.set_active_session(user_id, session_id)

    if not session_id:
        session = await session_service.create_session(user_id)
        session_id = session["session_id"]
        await redis_service.set_active_session(user_id, session_id)

    # LOAD MESSAGES
    messages = await redis_service.get_session_messages(session_id)

    if messages is None:
        session = await session_service.get_session(session_id, user_id)
        raw_messages = session.get("messages", []) if session else []
        messages = raw_messages or []
        await redis_service.set_session_messages(session_id, messages)

    logger.info(f"Messages loaded: {len(messages)}")

    # VALIDATE
    user_content = (payload.content or payload.message or "").strip()
    if not user_content:
        raise HTTPException(status_code=400, detail="Message required")

    logger.info(f"User message: {user_content}")

    # USER DATA FROM REDIS OR DB
    user_details = await redis_service.get_user_details(user_id)
    if not user_details:
        try:
            async with pool.acquire() as conn:
                user_row = await conn.fetchrow(
                    "SELECT * FROM users WHERE id = $1 OR email = $1 OR user_name = $1",
                    user_id
                )
                if user_row:
                    user_details = dict(user_row)
        except Exception as e:
            logger.warning(f"Error fetching user details from DB: {e}")

    if not user_details:
        user_details = {"id": user_id, "name": "User", "company_id": None}

    logger.info(f"User details: {user_details}")

    session_summary = await redis_service.get_session_summary(session_id)
    logger.info(f"Session summary from Redis: {session_summary}")

    # RUN CHAT (FIXED)
    t_chat_start = time.perf_counter()
    node_response, updated_messages, standalone_query, understanding_summary, extras = await chat_service.run_chat(
        user_id=user_id,
        session_id=session_id,
        db_messages=messages,
        current_query=user_content,
        category=payload.category,
        user_details=user_details,
        skip_clarification=payload.skip_clarification,
    )

    # Non-streaming PDF Vector Retrieval (Part 2)
    try:
        if not is_simple_social_intent(user_content):
            raw_pdf_chunks = await chat_service._retrieve_pdf_chunks(user_content, k=4)
            cleaned_pdf_chunks = []
            seen_p = set()
            for chunk in (raw_pdf_chunks or []):
                d_title = str(chunk.get("source_pdf") or chunk.get("title") or chunk.get("topic_name") or "Document").strip()
                p_url = str(chunk.get("pdf_url") or chunk.get("link") or "").strip()
                p_num = chunk.get("page") or 1
                k_key = f"{d_title}_{p_num}"
                if k_key in seen_p:
                    continue
                seen_p.add(k_key)
                score = float(chunk.get("_score") or chunk.get("score") or 0.0)
                cleaned_pdf_chunks.append({
                    "document": d_title,
                    "title": d_title,
                    "page": p_num,
                    "link": p_url,
                    "url": p_url,
                    "topic_code": str(chunk.get("topic_code") or ""),
                    "topic_name": str(chunk.get("topic_name") or ""),
                    "course_code": str(chunk.get("course_code") or ""),
                    "course_name": str(chunk.get("course_name") or ""),
                    "chunk_type": str(chunk.get("chunk_type") or "text"),
                    "score": round(score, 4),
                    "match_pct": round(max(0.0, min(100.0, score * 100)), 1) if score <= 1.0 else round(score, 1),
                    "text_preview": str(chunk.get("raw_text") or chunk.get("text") or "")[:350].strip(),
                    "images": list(chunk.get("image_refs") or [])[:4]
                })
                if len(cleaned_pdf_chunks) >= 4:
                    break
            node_response.matched_pdf_chunks = cleaned_pdf_chunks
            if updated_messages and isinstance(updated_messages[-1], dict) and updated_messages[-1].get("role") == "assistant":
                updated_messages[-1]["matched_pdf_chunks"] = cleaned_pdf_chunks
    except Exception as e:
        logger.debug(f"Non-fatal PDF vector retrieval error: {e}")

    logger.info(f"Updated messages count: {len(updated_messages)}")

    t_save_start = time.perf_counter()
    await redis_service.set_session_messages(session_id, updated_messages)
    logger.info("Redis updated successfully")

    await session_service.update_session_messages(session_id, updated_messages)
    logger.info("Saved to PostgreSQL")
    save_dur = time.perf_counter() - t_save_start

    total_dur = time.perf_counter() - t_chat_start
    latencies = (extras.get("latencies", {}) if isinstance(extras, dict) else {})
    print("\n" + "=" * 68)
    print(f"[LATENCY PROFILE] Query: \"{user_content[:45]}\"")
    print("=" * 68)
    if latencies:
        print(f"  |-- 1. Query Rewrite (OpenAI LLM)      : {latencies.get('query_rewrite', 0):.2f}s")
        print(f"  |-- 2. Intent Classification (LLM)     : {latencies.get('router_classify', 0):.2f}s")
        if 'initial_chunk_retrieval' in latencies:
            print(f"  |-- 3. Course Chunk Search (FAISS/BM25): {latencies.get('initial_chunk_retrieval', 0):.2f}s")
        if 'retrieval_node' in latencies:
            print(f"  |-- 4. Course Vector Retrieval (FAISS) : {latencies.get('retrieval_node', 0):.2f}s")
        if 'company_retrieval' in latencies:
            print(f"  |-- 5. Company Knowledge Retrieval     : {latencies.get('company_retrieval', 0):.2f}s")
        if 'answer_generation' in latencies:
            print(f"  |-- 6. Answer Generation (OpenAI LLM)  : {latencies.get('answer_generation', 0):.2f}s")
        if 'media_enrichment' in latencies:
            print(f"  |-- 7. Media & Sibling Lookup (DB)     : {latencies.get('media_enrichment', 0):.2f}s")
    print(f"  |-- 8. Redis & DB Session Save         : {save_dur:.2f}s")
    print("-" * 68)
    print(f"[TOTAL TIME] Total Response Time       : {total_dur:.2f}s")
    print("=" * 68 + "\n")

    logger.info("Chat success")

    if node_response and getattr(node_response, "question_suggestions", None):
        node_response.question_suggestions = [
            SuggestionService.to_suggestion_pair(item) for item in node_response.question_suggestions
        ]

    return node_response

@router.post("/switch-session")
async def switch_session(
    session_id: str,
    request: Request,
):
    user_id = request.cookies.get("marine_user_id", "anonymous")

    logger.info(f"Switching session for user {user_id} -> {session_id}")

    try:
        await redis_service.set_active_session(user_id, session_id)
        logger.info("Session switched in Redis")

    except Exception as e:
        logger.warning(f"Redis error while switching session: {e}")

    return {"message": "Session switched"}



@router.post("/working-stream")
@rate_limit_chat
async def chat1(
    request: Request,
    payload: TestChatMessage,
    background_tasks: BackgroundTasks,
    pool: Pool = Depends(get_db_pool),
    openai_service: OpenAIService = Depends(get_openai_service),
    embedder: EmbeddingService = Depends(get_embedding_service),
    store: FAISSStore = Depends(get_faiss_store),
    company_store: FAISSStore = Depends(get_company_store),
    transcribe_store: FAISSStore = Depends(get_transcribe_store),
):

    logger.info("New chat stream request received")

    session_service = SessionService(pool)
    chat_service = ChatService(
        openai_service,
        embedder,
        store,
        session_service,
        company_store=company_store,
        transcribe_store=transcribe_store,
    )

    user_id = payload.user_id or "test-user"

    # -----------------------------
    # SESSION
    # -----------------------------
    session_id = await redis_service.get_active_session(user_id)
    logger.info(f"Redis active session: {session_id}")

    if payload.session_id:
        session_id = payload.session_id
        await redis_service.set_active_session(user_id, session_id)

    if not session_id:
        session = await session_service.create_session(user_id)
        session_id = session["session_id"]

        await redis_service.set_active_session(
            user_id,
            session_id
        )

    # -----------------------------
    # LOAD MESSAGES
    # -----------------------------
    messages = await redis_service.get_session_messages(session_id)

    if messages is None:
        session = await session_service.get_session(
            session_id,
            user_id
        )

        raw_messages = session.get("messages", []) if session else []

        messages = raw_messages or []

        await redis_service.set_session_messages(session_id, messages)

    logger.info(f"Messages loaded: {len(messages)}")

    # -----------------------------
    # VALIDATE
    # -----------------------------
    user_content = (payload.content or payload.message or "").strip()

    if not user_content:
        raise HTTPException(status_code=400, detail="Message required")

    logger.info(f"User message: {user_content}")

    user_details = await redis_service.get_user_details(user_id)
    if not user_details:
        try:
            async with pool.acquire() as conn:
                user_row = await conn.fetchrow(
                    "SELECT * FROM users WHERE id = $1 OR email = $1 OR user_name = $1",
                    user_id
                )
                if user_row:
                    user_details = dict(user_row)
        except Exception as e:
            logger.warning(f"Error fetching user details from DB: {e}")

    if not user_details:
        user_details = {
            "id": user_id,
            "name": payload.name or "User",
            "role": payload.role or None,
            "ship_name": payload.ship or None,
            "ship_type": payload.ship_type or None,
            "company_name": payload.company or None,
            "company_id": None,
        }

    logger.info(f"User details: {user_details}")

    company_id = user_details.get("company_id") if isinstance(user_details, dict) else None
    logger.info(f"Company ID: {company_id}")

    session_summary = await redis_service.get_session_summary(session_id)
    logger.info(f"Session summary from Redis: {session_summary}")

    async def stream_response():

        try:

            # -----------------------------
            # STEP 1: STATUS STREAMING QUEUE
            # -----------------------------
            # STEP 1: STATUS & REAL-TIME EVENT STREAMING QUEUE
            # -----------------------------
            status_queue: asyncio.Queue = asyncio.Queue()

            async def stream_event_callback(event_data: dict):
                try:
                    await status_queue.put(event_data)
                except Exception:
                    pass

            async def status_callback(stage: str, message: str):
                try:
                    await status_queue.put({"type": "status", "stage": stage, "message": message})
                except Exception:
                    pass

            await status_callback("thinking", "Dolphin is thinking...")

            # -----------------------------
            # STEP 2: CHAT PIPELINE TASK
            # -----------------------------
            chat_task = asyncio.create_task(
                chat_service.run_chat(
                    user_id=user_id,
                    session_id=session_id,
                    db_messages=messages,
                    current_query=user_content,
                    category=payload.category,
                    user_details=user_details,
                    status_callback=status_callback,
                    stream_callback=stream_event_callback,
                    skip_clarification=payload.skip_clarification,
                )
            )

            t_stream_start = time.perf_counter()
            transcript_dur = 0.0
            pdf_dur = 0.0
            is_social_query = bool(is_simple_social_intent(user_content))
            transcript_task: Optional[asyncio.Task] = None
            pdf_task: Optional[asyncio.Task] = None

            if not is_social_query:
                async def transcript_search():
                    nonlocal transcript_dur
                    try:
                        logger.info("Preparing transcript search...")
                        t_tr = time.perf_counter()
                        transcript_chunks = await chat_service._retrieve_transcript_chunks(
                            user_content
                        )
                        transcript_dur = time.perf_counter() - t_tr
                        logger.info(
                            f"[Timer] Transcript Search returned {len(transcript_chunks)} chunks in {transcript_dur:.2f}s"
                        )

                        return transcript_chunks

                    except Exception:
                        logger.exception("Transcript search failed")
                        return []

                transcript_task = asyncio.create_task(
                    transcript_search()
                )

                async def pdf_vector_search():
                    nonlocal pdf_dur
                    try:
                        logger.info("Preparing PDF vector search...")
                        t_pdf = time.perf_counter()
                        chunks = await chat_service._retrieve_pdf_chunks(user_content, k=4)
                        pdf_dur = time.perf_counter() - t_pdf
                        logger.info(
                            f"[Timer] PDF Vector Search returned {len(chunks)} chunks in {pdf_dur:.2f}s"
                        )
                        return chunks
                    except Exception:
                        logger.exception("PDF vector search failed")
                        return []

                pdf_task = asyncio.create_task(
                    pdf_vector_search()
                )
            else:
                logger.info("⚡ [Router] Skipped transcript video search for social query")

            # Stream status, source_topic, and content events as they arrive while chat_task is running
            tokens_streamed = False
            while not chat_task.done() or not status_queue.empty():
                try:
                    event_item = await asyncio.wait_for(status_queue.get(), timeout=0.04)
                    if event_item.get("type") == "content":
                        tokens_streamed = True
                    yield f"data: {json.dumps(event_item)}\n\n"
                except asyncio.TimeoutError:
                    continue

            # Flush any remaining events
            while not status_queue.empty():
                event_item = status_queue.get_nowait()
                if event_item.get("type") == "content":
                    tokens_streamed = True
                yield f"data: {json.dumps(event_item)}\n\n"

            (
                node_response,
                updated_messages,
                _,
                _,
                media
            ) = await chat_task

           
            sections = node_response.sections or []

            clarification_payload = (node_response.metadata or {}).get("clarification")
            is_clarification = bool(clarification_payload)
            # clarification questions and "general overview" answers carry no course media
            suppress_extras = is_clarification or (node_response.metadata or {}).get("general_overview") is True

            is_stream_out_of_scope = (
                (node_response.metadata or {}).get("out_of_scope") is True
                or getattr(node_response, "category", "") in ("FALLBACK", "OFF_TOPIC")
                or any(
                    s.get("topic_name", "").strip().lower() in ("out of scope", "off topic", "unrelated")
                    or "outside the marine training curriculum" in s.get("content", "").lower()
                    or "outside the maritime curriculum" in s.get("content", "").lower()
                    or "specialized exclusively in maritime" in s.get("content", "").lower()
                    or ("marine tutor ai" in s.get("content", "").lower() and "outside" in s.get("content", "").lower())
                    for s in sections
                )
            )

            # If tokens were not streamed in real-time (e.g. social greeting or fallback node), emit them now
            if not tokens_streamed:
                if sections:
                    for idx, section in enumerate(sections):
                        if idx > 0:
                            separator_data = {"type": "content", "token": "\n\n"}
                            yield f"data: {json.dumps(separator_data)}\n\n"

                        topic_name = section.get("topic_name") or ""
                        if is_stream_out_of_scope or topic_name.strip().lower() in ("out of scope", "off topic", "unrelated"):
                            topic_name = ""

                        source_data = {
                            "type": "source_topic",
                            "topic_code": "" if is_stream_out_of_scope else section.get("topic_code"),
                            "topic_name": topic_name
                        }

                        yield f"data: {json.dumps(source_data)}\n\n"

                        content = section.get("content", "")
                        if is_stream_out_of_scope:
                            content = re.sub(r'^(?:#{1,6}\s*|\*{2})?(?:Out of Scope|Off Topic)(?:\*{2})?[:\s]*\n*', '', content, flags=re.IGNORECASE).strip()

                        tokens = re.findall(r'\S+\s*|\n+', content) if content else []
                        for token in tokens:
                            content_data = {
                                "type": "content",
                                "token": token
                            }
                            yield f"data: {json.dumps(content_data)}\n\n"
                            await asyncio.sleep(0)

                else:
                    content = node_response.content or ""
                    if is_stream_out_of_scope:
                        content = re.sub(r'^(?:#{1,6}\s*|\*{2})?(?:Out of Scope|Off Topic)(?:\*{2})?[:\s]*\n*', '', content, flags=re.IGNORECASE).strip()

                    tokens = re.findall(r'\S+\s*|\n+', content) if content else []
                    for token in tokens:
                        content_data = {
                            "type": "content",
                            "token": token
                        }
                        yield f"data: {json.dumps(content_data)}\n\n"
                        await asyncio.sleep(0)

            # suggestions (structured pairs of 2-3 word label and full query)
            raw_suggestions = node_response.question_suggestions or []
            paired_suggestions = [
                SuggestionService.to_suggestion_pair(item) for item in raw_suggestions
            ]
            suggestions_payload = {
                "type": "suggestions",
                "question_suggestions": paired_suggestions,
            }

            yield (
                f"data: {json.dumps(suggestions_payload)}\n\n"
            )

            # "Did you mean...?" - structured options so the UI can render chips
            if is_clarification and isinstance(clarification_payload, dict):
                yield (
                    "data: "
                    + json.dumps({"type": "clarification", **clarification_payload})
                    + "\n\n"
                )

            is_resp_social = (
                is_social_query
                or getattr(node_response, "type", "") in ("greeting", "goodbye", "thank", "well_wish")
                or (node_response.metadata or {}).get("category") in ("GREETING", "GOODBYE", "THANK", "WELL_WISH")
                or getattr(node_response, "category", "") in ("GREETING", "GOODBYE", "THANK", "WELL_WISH")
            )

            resp_content_str = " ".join(getattr(s, "content", "") for s in getattr(node_response, "sections", [])).lower()
            is_course_missing = any(neg in resp_content_str for neg in [
                "not available in the curriculum",
                "not detailed in the provided course",
                "not explicitly stated in the provided course",
                "not present in the provided course",
                "does not contain information",
                "does not contain a specific module",
                "does not cover",
            ])

            if is_stream_out_of_scope or is_resp_social or suppress_extras or is_course_missing:
                media_videos = []
                media_images = []
                media_pdfs = []
                media_topic_codes = []
            else:
                # The final filtered media payload is authoritative.
                # If scope filtering returns an empty list, keep it empty and do NOT fall back to node_response.
                media_videos = media["videos"] if (isinstance(media, dict) and "videos" in media) else (getattr(node_response, "videos", None) or [])
                media_images = media["images"] if (isinstance(media, dict) and "images" in media) else (getattr(node_response, "images", None) or [])
                media_pdfs = media["pdfs"] if (isinstance(media, dict) and "pdfs" in media) else (getattr(node_response, "pdfs", None) or [])
                media_topic_codes = media.get("topic_codes", []) if isinstance(media, dict) else (getattr(node_response, "topic_codes", None) or [])

            extracted_topics = []
            seen_t_keys = set()
            for s in (sections or []):
                tc = str(s.get("topic_code") or "").strip()
                tn = str(s.get("topic_name") or "").strip()
                c_code = str(s.get("course_code") or s.get("CourseCode") or "").strip()
                c_name = str(s.get("course_name") or s.get("CourseName") or "").strip()
                if tc or tn:
                    key = tc or tn
                    if key not in seen_t_keys:
                        seen_t_keys.add(key)
                        extracted_topics.append({
                            "code": tc,
                            "name": tn,
                            "course_code": c_code,
                            "course_name": c_name,
                        })

            for v in (media_videos or []):
                tc = str(v.get("topic_code") or "").strip()
                tn = str(v.get("topic_name") or "").strip()
                c_code = str(v.get("course_code") or v.get("CourseCode") or "").strip()
                c_name = str(v.get("course_name") or v.get("CourseName") or "").strip()
                if tc or tn:
                    key = tc or tn
                    if key not in seen_t_keys:
                        seen_t_keys.add(key)
                        extracted_topics.append({
                            "code": tc,
                            "name": tn,
                            "course_code": c_code,
                            "course_name": c_name,
                        })

            if not extracted_topics and media_topic_codes:
                for tc in media_topic_codes:
                    if tc and str(tc) not in seen_t_keys:
                        seen_t_keys.add(str(tc))
                        extracted_topics.append({
                            "code": str(tc),
                            "name": f"Topic {tc}",
                            "course_code": "",
                            "course_name": "",
                        })

            if not is_stream_out_of_scope and not is_resp_social and not suppress_extras:
                media_payload = {
                    "type": "media",
                    "videos": media_videos[:5],
                    "images": media_images[:5],
                    "pdfs": media_pdfs[:5],
                    "topic_codes": media_topic_codes,
                    "topics": extracted_topics,
                }

                yield (
                    f"data: {json.dumps(media_payload)}\n\n"
                )

                for top in extracted_topics:
                    yield f"data: {json.dumps({'type': 'source_topic', 'topic_code': top['code'], 'topic_name': top['name']})}\n\n"

            company_answer = None if (is_stream_out_of_scope or is_resp_social or suppress_extras) else media.get("company_answer")

            if company_answer:
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "company_content",
                            "content": company_answer,
                        }
                    )
                    + "\n\n"
                )

            # -----------------------------
            # TRANSCRIPT RESULT
            # -----------------------------
            if is_stream_out_of_scope or is_resp_social or suppress_extras or transcript_task is None:
                if transcript_task is not None and not transcript_task.done():
                    transcript_task.cancel()
                transcript_chunks = []
            else:
                transcript_chunks = await transcript_task

            stream_scope = (
                (media.get("question_scope") if isinstance(media, dict) else None)
                or (node_response.metadata or {}).get("question_scope")
                or "GENERAL"
            )
            from services.question_scope import extract_specific_subject_terms, SCOPE_SPECIFIC
            specific_terms = extract_specific_subject_terms(user_content) if stream_scope == SCOPE_SPECIFIC else set()

            unique_chunks = []
            seen_videos = set()
            query_lower = (user_content or "").lower()
            query_asked_intro = any(w in query_lower for w in ["intro", "introduction", "overview", "basics", "summary"])
            from services.maritime_acronyms import expand_query_terms_for_media, has_conflicting_acronym
            effective_terms = expand_query_terms_for_media(user_content)

            for chunk in transcript_chunks:
                video_id = str(chunk.get("video_id") or chunk.get("video_link") or chunk.get("Url") or chunk.get("url") or "").strip()
                link = str(chunk.get("video_link") or chunk.get("Url") or chunk.get("url") or "").strip()
                title = str(chunk.get("video_title") or chunk.get("Title") or chunk.get("title") or "").strip()

                if not video_id or video_id in seen_videos:
                    continue
                # Discard broken video URLs
                if not link or link.lower() in ("none", "null", "undefined", ""):
                    continue
                if not (link.startswith("http://") or link.startswith("https://") or link.endswith(".mp4")):
                    continue

                title_lower = title.lower()
                # Check for conflicting acronym
                if has_conflicting_acronym(user_content, title_lower):
                    continue

                # Filter out generic intro videos if query didn't ask for intro or if query is specific
                is_intro = any(w in title_lower for w in ["introduction", "intro to", "overview", "course overview", "welcome", "module overview"])
                if is_intro:
                    if stream_scope == SCOPE_SPECIFIC or not query_asked_intro:
                        has_match = any(qw in title_lower for qw in effective_terms) if (effective_terms and stream_scope != SCOPE_SPECIFIC) else False
                        if not has_match:
                            continue

                # Specific scope relevance check:
                if stream_scope == SCOPE_SPECIFIC and specific_terms:
                    chunk_text = f"{title_lower} {str(chunk.get('content') or '').lower()}"
                    has_spec_match = any(
                        re.search(r'\b' + re.escape(st) + r'\b', chunk_text)
                        for st in specific_terms
                    )
                    if not has_spec_match:
                        continue
                elif effective_terms:
                    # General / fallback relevance check:
                    chunk_text = f"{title_lower} {str(chunk.get('content') or '').lower()}"
                    has_term_match = any(qw in chunk_text for qw in effective_terms)
                    if not has_term_match:
                        continue

                seen_videos.add(video_id)
                if isinstance(chunk, dict):
                    chunk["source_type"] = "transcript_vector"
                    chunk["topic_code"] = str(chunk.get("topic_code") or "")
                    chunk["course_code"] = str(chunk.get("course_code") or "")
                unique_chunks.append(chunk)
                if len(unique_chunks) >= 5:
                    break

            if not is_stream_out_of_scope and not is_resp_social and not suppress_extras and not is_course_missing and unique_chunks:
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "transcript_result",
                            "chunks": unique_chunks,
                        }
                    )
                    + "\n\n"
                )

            # -----------------------------
            # PDF VECTOR RESULT (PART 2)
            # -----------------------------
            if is_stream_out_of_scope or is_resp_social or suppress_extras or is_course_missing or pdf_task is None:
                if pdf_task is not None and not pdf_task.done():
                    pdf_task.cancel()
                raw_pdf_chunks = []
            else:
                raw_pdf_chunks = await pdf_task

            unique_pdf_chunks = []
            seen_pdf_keys = set()
            for chunk in (raw_pdf_chunks or []):
                doc_title = str(chunk.get('source_pdf') or chunk.get('title') or chunk.get('topic_name') or 'Document').strip()
                pdf_url = str(chunk.get('pdf_url') or chunk.get('link') or '').strip()
                page = chunk.get('page') or 1
                score = float(chunk.get('_score') or chunk.get('score') or 0.0)
                dedup_key = f"{doc_title}_{page}"
                if dedup_key in seen_pdf_keys:
                    continue
                seen_pdf_keys.add(dedup_key)

                cleaned_chunk = {
                    'document': doc_title,
                    'title': doc_title,
                    'page': page,
                    'link': pdf_url,
                    'url': pdf_url,
                    'topic_code': str(chunk.get('topic_code') or ''),
                    'topic_name': str(chunk.get('topic_name') or ''),
                    'course_code': str(chunk.get('course_code') or ''),
                    'course_name': str(chunk.get('course_name') or ''),
                    'chunk_type': str(chunk.get('chunk_type') or 'text'),
                    'score': round(score, 4),
                    'match_pct': round(max(0.0, min(100.0, score * 100)), 1) if score <= 1.0 else round(score, 1),
                    'text_preview': str(chunk.get('raw_text') or chunk.get('text') or '')[:350].strip(),
                    'images': list(chunk.get('image_refs') or [])[:4]
                }
                unique_pdf_chunks.append(cleaned_chunk)
                if len(unique_pdf_chunks) >= 4:
                    break

            if not is_stream_out_of_scope and not is_resp_social and not suppress_extras and not is_course_missing and unique_pdf_chunks:
                yield (
                    'data: '
                    + json.dumps(
                        {
                            'type': 'pdf_result',
                            'chunks': unique_pdf_chunks,
                        }
                    )
                    + '\n\n'
                )

                        
            # Attach rich media, transcripts, and topics to saved session message
            if updated_messages and isinstance(updated_messages[-1], dict) and updated_messages[-1].get("role") == "assistant":
                if unique_chunks:
                    updated_messages[-1]["transcripts"] = unique_chunks
                if unique_pdf_chunks:
                    updated_messages[-1]["matched_pdf_chunks"] = unique_pdf_chunks
                if extracted_topics:
                    updated_messages[-1]["topics"] = extracted_topics
                if media_topic_codes:
                    updated_messages[-1]["topic_codes"] = media_topic_codes
                if media_videos:
                    updated_messages[-1]["videos"] = media_videos[:5]

            # -----------------------------
            # SAVE (Concurrent Redis + PostgreSQL)
            # -----------------------------
            t_save_start = time.perf_counter()
            await asyncio.gather(
                redis_service.set_session_messages(
                    session_id,
                    updated_messages
                ),
                session_service.update_session_messages(
                    session_id,
                    updated_messages
                )
            )

            logger.info("Redis & PostgreSQL session messages updated concurrently")
            save_dur = time.perf_counter() - t_save_start

            total_dur = time.perf_counter() - t_stream_start

            # Print latency breakdown to terminal
            latencies = (media.get("latencies", {}) if isinstance(media, dict) else {})
            print("\n" + "=" * 68)
            print(f"[LATENCY PROFILE] Query: \"{user_content[:45]}\"")
            print("=" * 68)
            if latencies:
                print(f"  |-- 1. Query Rewrite (OpenAI LLM)      : {latencies.get('query_rewrite', 0):.2f}s")
                print(f"  |-- 2. Intent Classification (LLM)     : {latencies.get('router_classify', 0):.2f}s")
                if 'initial_chunk_retrieval' in latencies:
                    print(f"  |-- 3. Course Chunk Search (FAISS/BM25): {latencies.get('initial_chunk_retrieval', 0):.2f}s")
                if 'retrieval_node' in latencies:
                    print(f"  |-- 4. Course Vector Retrieval (FAISS) : {latencies.get('retrieval_node', 0):.2f}s")
                if 'company_retrieval' in latencies:
                    print(f"  |-- 5. Company Knowledge Retrieval     : {latencies.get('company_retrieval', 0):.2f}s")
                if 'answer_generation' in latencies:
                    print(f"  |-- 6. Answer Generation (OpenAI LLM)  : {latencies.get('answer_generation', 0):.2f}s")
                if 'media_enrichment' in latencies:
                    print(f"  |-- 7. Media & Sibling Lookup (DB)     : {latencies.get('media_enrichment', 0):.2f}s")
            print(f"  |-- 8. Transcript Video Search (FAISS) : {transcript_dur:.2f}s")
            print(f"  |-- 9. Redis & DB Session Save         : {save_dur:.2f}s")
            print("-" * 68)
            print(f"[TOTAL TIME] Total Response Time       : {total_dur:.2f}s")
            print("=" * 68 + "\n")

            logger.info("Stream complete")

        except Exception as e:

            logger.error(f"Stream error: {e}")

            error_payload = {
                "type": "error",
                "message": str(e)
            }

            yield (
                f"data: {json.dumps(error_payload)}\n\n"
            )

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Encoding": "identity",
        }
    )

