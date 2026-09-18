import asyncio
import json
import re
import time
from datetime import datetime
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
from models.database import get_pool
from pipeline.retrieval import compute_video_relevance_score
from services.scope_messages import is_out_of_scope_text
from services.status_service import get_status_event
from api.course_router import check_topic_course, CheckTopicCourseRequest

router = APIRouter(prefix="/chat", tags=["chat"])
MAX_MESSAGE_LENGTH = 4000
class ChatMessage(BaseModel):
    content: Optional[str] = None
    message: Optional[str] = None
    category: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class TestChatMessage(BaseModel):
    content: Optional[str] = None
    message: Optional[str] = None
    category: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None

    # directly pass from frontend / login api
    name: Optional[str] = ""
    role: Optional[str] = ""
    ship: Optional[str] = ""
    ship_type: Optional[str] = ""
    company: Optional[str] = ""    

@router.post("/legacy", response_model=NodeResponse)
@rate_limit_chat
async def chat_legacy(
    request: Request,
    payload: ChatMessage,
    background_tasks: BackgroundTasks,
    pool: Pool = Depends(get_db_pool),
    openai_service: OpenAIService = Depends(get_openai_service),
    embedder: EmbeddingService = Depends(get_embedding_service),
    store: FAISSStore = Depends(get_faiss_store),
) -> NodeResponse:

    print("\n===== NEW CHAT REQUEST =====")

    session_service = SessionService(pool)
    chat_service = ChatService(openai_service, embedder, store, session_service)

    # user_id = request.cookies.get("marine_user_id", "anonymous")
    # print(f"User ID: {user_id}")
    user_id = payload.user_id or "anonymous"

    # SESSION

    session_id = await redis_service.get_active_session(user_id)
    print(f"Redis active session: {session_id}")

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

    print(f"Messages loaded: {len(messages)}")

    # VALIDATE

    user_content = (payload.content or payload.message or "").strip()
    if not user_content:
        raise HTTPException(status_code=400, detail="Message required")

    print(f"User message: {user_content}")

    # USER DATA FROM REDIS (IMPORTANT)
  
    user_details = await redis_service.get_user_details(user_id)
    if not user_details and user_id and user_id != "anonymous" and user_id != "guest":
        try:
            async with pool.acquire() as conn:
                record = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
                if record:
                    row_dict = dict(record)
                    user_details = {
                        "id": str(row_dict.get("id")),
                        "name": row_dict.get("name"),
                        "email": row_dict.get("email"),
                        "role": row_dict.get("role"),
                        "company_name": row_dict.get("company_name"),
                        "company_id": row_dict.get("company_id"),
                        "user_type": row_dict.get("user_type"),
                        "ship_name": row_dict.get("ship_name"),
                        "ship_type": row_dict.get("ship_type"),
                        "user_courses": row_dict.get("user_courses")
                    }
                    await redis_service.set_user_data(user_id, user_details)
        except Exception as ex:
            logger.warning(f"Failed to fetch user from DB: {ex}")
    logger.debug(f"User details loaded for user_id={user_id}")

    session_summary = await redis_service.get_session_summary(session_id)
    print(f"Session summary from Redis: {session_summary}")

    # RUN CHAT (FIXED)
  
    node_response, updated_messages, standalone_query, understanding_summary, extras= await chat_service.run_chat(
        user_id=user_id,
        session_id=session_id,
        db_messages=messages,
        current_query=user_content,
        category=payload.category,
        user_details=user_details
    )

    print(f"Updated messages count: {len(updated_messages)}")

    if updated_messages and isinstance(updated_messages[-1], dict) and updated_messages[-1].get("role") == "assistant":
        node_meta = getattr(node_response, "metadata", None) or {}
        is_non_query = (
            node_meta.get("category") in {"GREETING", "GOODBYE", "THANK", "WELL_WISH", "FALLBACK", "GAP_ANALYSIS_REQUEST", "OUT_OF_SCOPE"}
            or node_meta.get("routing_reason") == "out_of_scope"
            or bool(node_meta.get("requires_upload"))
            or is_out_of_scope_text(node_response.content)
        )
        if is_non_query:
            updated_messages[-1]["videos"] = []
            updated_messages[-1]["images"] = []
            updated_messages[-1]["pdfs"] = []
            updated_messages[-1]["checkLicCoursesData"] = []
            updated_messages[-1]["courses"] = []
        elif isinstance(extras, dict):
            updated_messages[-1]["videos"] = list(extras.get("videos", [])[:5])
            updated_messages[-1]["images"] = list(extras.get("images", [])[:6])
            updated_messages[-1]["pdfs"] = list(extras.get("pdfs", [])[:2])
            if getattr(node_response, "question_suggestions", None):
                updated_messages[-1]["question_suggestions"] = list(node_response.question_suggestions)

            sections = getattr(node_response, "sections", None) or []
            raw_codes = []
            if sections:
                for s in sections:
                    if isinstance(s, dict) and s.get("topic_code"):
                        raw_codes.append((str(s["topic_code"]).strip(), str(s.get("topic_name") or "").strip()))
            if extras and isinstance(extras.get("topic_codes"), list):
                for tc in extras["topic_codes"]:
                    if tc:
                        raw_codes.append((str(tc).strip(), ""))

            seen_codes = set()
            valid_topic_codes = []
            for c, t_name in raw_codes:
                c_clean = c.strip()
                c_upper = c_clean.upper()
                if c_clean and c_upper not in {"COMPANY_SMS", "GAP_ANALYSIS", "NONE"} and c_clean not in seen_codes:
                    seen_codes.add(c_clean)
                    valid_topic_codes.append((c_clean, t_name))

            courses_data = []
            for code, t_name in valid_topic_codes:
                try:
                    res = await check_topic_course(
                        CheckTopicCourseRequest(
                            topic_code=code,
                            user_id=user_id
                        ),
                        pool=pool
                    )
                    if res and isinstance(res, dict) and res.get("data") and res["data"].get("course"):
                        if t_name and not res["data"].get("topic_name"):
                            res["data"]["topic_name"] = t_name
                        courses_data.append(res)
                except Exception as err:
                    logger.warning(f"Error checking topic course for {code}: {err}")

            updated_messages[-1]["checkLicCoursesData"] = courses_data
            updated_messages[-1]["courses"] = courses_data
            updated_messages[-1]["sections"] = sections
            updated_messages[-1]["topic_codes"] = [c for c, _ in valid_topic_codes]

    await redis_service.set_session_messages(session_id, updated_messages)
    print("Redis updated successfully")

    await session_service.update_session_messages(session_id, updated_messages)
    print("Saved to PostgreSQL")

    print("===== CHAT SUCCESS =====\n")

    return node_response

@router.post("/switch-session")
async def switch_session(
    session_id: str,
    request: Request,
):
    user_id = request.cookies.get("marine_user_id", "anonymous")

    print(f"🔄 Switching session for user {user_id} → {session_id}")

    try:
        await redis_service.set_active_session(user_id, session_id)
        print("✅ Session switched in Redis")

    except Exception as e:
        print(f"❌ Redis error while switching session: {e}")

    return {"message": "Session switched"}



@router.post("")
@rate_limit_chat
async def chat(
    request: Request,
    payload: TestChatMessage,
    background_tasks: BackgroundTasks,
    pool: Pool = Depends(get_db_pool),
    openai_service: OpenAIService = Depends(get_openai_service),
    embedder: EmbeddingService = Depends(get_embedding_service),
    store: FAISSStore = Depends(get_faiss_store),
):

    print("\n🚀 ===== NEW CHAT REQUEST =====")

    session_service = SessionService(pool)
    chat_service = ChatService(
        openai_service,
        embedder,
        store,
        session_service
    )

    # user_id = request.cookies.get("marine_user_id", "anonymous")
    # print(f"👤 User ID: {user_id}")

    # user_id = payload.user_id or "anonymous"
    user_id = payload.user_id or "test-user"

    # -----------------------------
    # 🔹 SESSION
    # -----------------------------
    session_id = await redis_service.get_active_session(user_id)
    print(f"🔹 Redis active session: {session_id}")

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
    # 🔹 LOAD MESSAGES
    # -----------------------------
    messages = await redis_service.get_session_messages(session_id)

    if messages is None:
        session = await session_service.get_session(
            session_id,
            user_id
        )

        raw_messages = session.get("messages", []) if session else []

        messages = raw_messages or []

        await redis_service.set_session_messages(session_id,messages)

    print(f"📥 Messages loaded: {len(messages)}")

    # -----------------------------
    # 🔹 VALIDATE
    # -----------------------------
    user_content = (payload.content or payload.message or "").strip()

    if not user_content:
        raise HTTPException(status_code=400,detail="Message required")

    print(f"💬 User message: {user_content}")

    user_details = await redis_service.get_user_details(user_id) or {}
    logger.debug(f"User details loaded from Redis for user_id={user_id}")

    # Fallback: if Redis is disconnected or missing user details, fetch from PostgreSQL users table
    if not user_details.get("company_id") and user_id and user_id != "anonymous":
        try:
            async with pool.acquire() as conn:
                user_row = await conn.fetchrow(
                    "SELECT company_id, company_name, name, email, role, user_type, ship_name, ship_type, user_courses FROM users WHERE id = $1",
                    user_id
                )
                if user_row:
                    user_details = {
                        "id": user_id,
                        "name": user_row.get("name") or "",
                        "email": user_row.get("email") or "",
                        "role": user_row.get("role") or "",
                        "user_type": user_row.get("user_type") or "",
                        "company_id": user_row.get("company_id"),
                        "company_name": user_row.get("company_name") or "",
                        "ship_name": user_row.get("ship_name") or "",
                        "ship_type": user_row.get("ship_type") or "",
                        "user_courses": user_row.get("user_courses")
                    }
                    existing_cached = await redis_service.get_user_data(user_id)
                    if existing_cached and existing_cached.get("company_courses"):
                        user_details["company_courses"] = existing_cached["company_courses"]
                    logger.debug(f"Fallback: Loaded user details from PostgreSQL for user_id={user_id}")
                    await redis_service.set_user_data(user_id, user_details)
        except Exception as e:
            logger.warning(f"❌ Failed to fetch user details fallback from PostgreSQL: {e}")

    # Dynamic resolution: if user has company_name but missing company_id, resolve from DB
    if not user_details.get("company_id") and user_details.get("company_name"):
        try:
            async with pool.acquire() as conn:
                cid_row = await conn.fetchrow(
                    "SELECT company_id FROM users WHERE LOWER(company_name) = LOWER($1) AND company_id IS NOT NULL LIMIT 1",
                    user_details.get("company_name")
                )
                if cid_row and cid_row.get("company_id"):
                    user_details["company_id"] = str(cid_row["company_id"])
                    print(f"Dynamically resolved company_id: {user_details['company_id']} for {user_details.get('company_name')}")
        except Exception as e:
            print(f"Could not dynamically resolve company_id: {e}")

    company_id = user_details.get("company_id")
    print(company_id)

    session_summary = await redis_service.get_session_summary(session_id)

    print(f"🧠 Session summary from Redis: {session_summary}")

    async def stream_response():

        t_stream_start = time.perf_counter()
        try:

            print("✅ STREAM STARTED")
            yield f"data: {json.dumps({'type': 'init', 'session_id': session_id})}\n\n"
            yield f"data: {json.dumps(get_status_event('understanding'))}\n\n"

            # -----------------------------
            # 🧠 STEP 1: CLEAN + REWRITE
            # -----------------------------
            cleaned_messages = chat_service._clean_messages(
                messages
            )

            previous_questions = [
                m.get("content")
                for m in cleaned_messages
                if m.get("role") == "user"
            ]

            # Find the most relevant substantive assistant answer (skip generic out-of-scope rejections)
            last_answer = None
            out_of_scope_patterns = [
                "not included in the current course content",
                "out of scope",
                "please ask a question relevant to the marine",
            ]
            for m in reversed(cleaned_messages):
                if m.get("role") == "assistant" and m.get("content"):
                    c_text = str(m.get("content", "")).lower()
                    if not any(pat in c_text for pat in out_of_scope_patterns):
                        last_answer = m.get("content")
                        break
            if not last_answer:
                last_answer = next(
                    (
                        m.get("content")
                        for m in reversed(cleaned_messages)
                        if m.get("role") == "assistant"
                    ),
                    None
                )

            t_rew_start = time.perf_counter()
            standalone_query = await chat_service.rewrite_query(
                current_query=user_content,
                previous_questions=previous_questions,
                last_answer=last_answer
            )
            t_rew_duration = time.perf_counter() - t_rew_start
            logger.info(f"⚡ [Chat Router] Query rewrite finished in {t_rew_duration:.3f}s: '{standalone_query}'")

            # Token queue for streaming real-time LLM content
            token_queue: asyncio.Queue = asyncio.Queue()
            t_first_token = [None]
            t_first_ui_token = [None]

            async def on_token_callback(event: dict):
                if t_first_token[0] is None and event.get("type") == "content":
                    t_first_token[0] = time.perf_counter() - t_stream_start
                    logger.info(f"⚡ [FIRST TOKEN] LLM generated first token at {t_first_token[0]:.3f}s from request start")
                await token_queue.put(event)

            # Start Chat Pipeline (with streaming callback) and Transcript search concurrently
            chat_task = asyncio.create_task(
                chat_service.run_chat(
                    user_id=user_id,
                    session_id=session_id,
                    db_messages=messages,
                    current_query=user_content,
                    category=payload.category,
                    user_details=user_details,
                    standalone_query=standalone_query,
                    on_token=on_token_callback,
                )
            )

            async def transcript_search():
                try:
                    logger.info("🎥 Preparing transcript search...")
                    transcript_chunks = await chat_service._retrieve_transcript_chunks(
                        standalone_query
                    )
                    logger.info(
                        f"🎥 Transcript Search returned {len(transcript_chunks)} chunks"
                    )
                    return transcript_chunks
                except Exception:
                    logger.exception("❌ Transcript search failed")
                    return []

            transcript_task = asyncio.create_task(
                transcript_search()
            )

            # -----------------------------
            # 🤖 LIVE STREAMING FROM CHAT PIPELINE (ZERO-LATENCY REAL-TIME STREAM)
            # -----------------------------
            streamed_any_content = False
            while not chat_task.done() or not token_queue.empty():
                try:
                    event = await asyncio.wait_for(token_queue.get(), timeout=0.01)
                    if event:
                        if event.get("type") == "content":
                            streamed_any_content = True
                            if t_first_ui_token[0] is None:
                                t_first_ui_token[0] = time.perf_counter() - t_stream_start
                            token_parts = [event.get("token", "")]
                            # Drain any currently queued content tokens immediately
                            while not token_queue.empty():
                                try:
                                    next_event = token_queue.get_nowait()
                                    if next_event.get("type") == "content":
                                        token_parts.append(next_event.get("token", ""))
                                    else:
                                        # Non-content event: flush current text and emit next_event
                                        combined_text = "".join(token_parts)
                                        if combined_text:
                                            yield f"data: {json.dumps({'type': 'content', 'token': combined_text})}\n\n"
                                        token_parts = []
                                        yield f"data: {json.dumps(next_event)}\n\n"
                                except asyncio.QueueEmpty:
                                    break
                            combined_text = "".join(token_parts)
                            if combined_text:
                                yield f"data: {json.dumps({'type': 'content', 'token': combined_text})}\n\n"
                            continue
                        yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    continue

            (
                node_response,
                updated_messages,
                _,
                _,
                media
            ) = await chat_task

            # Drain any remaining tokens/status events from queue
            remaining_content_parts = []
            while not token_queue.empty():
                try:
                    event = token_queue.get_nowait()
                    if event.get("type") == "content":
                        streamed_any_content = True
                        remaining_content_parts.append(event.get("token", ""))
                    else:
                        if remaining_content_parts:
                            combined_text = "".join(remaining_content_parts)
                            yield f"data: {json.dumps({'type': 'content', 'token': combined_text})}\n\n"
                            remaining_content_parts = []
                        yield f"data: {json.dumps(event)}\n\n"
                except asyncio.QueueEmpty:
                    break
            if remaining_content_parts:
                combined_text = "".join(remaining_content_parts)
                yield f"data: {json.dumps({'type': 'content', 'token': combined_text})}\n\n"

            sections = getattr(node_response, "sections", None) or []

            # If no content tokens were emitted during live streaming (e.g. non-streaming fallback)
            if not streamed_any_content:
                if sections:
                    for section in sections:
                        source_data = {
                            "type": "source_topic",
                            "topic_code": section.get("topic_code"),
                            "source_code": section.get("source_code") or section.get("course_code") or "",
                            "topic_name": section.get("topic_name")
                        }
                        yield f"data: {json.dumps(source_data)}\n\n"

                        content_str = section.get("content", "") or ""
                        if content_str:
                            yield f"data: {json.dumps({'type': 'content', 'token': content_str})}\n\n"
                else:
                    content_str = node_response.content or ""
                    if content_str:
                        yield f"data: {json.dumps({'type': 'content', 'token': content_str})}\n\n"
            else:
                # If content was streamed live, emit source_topic headers for any sections so badges can attach
                if sections:
                    for section in sections:
                        if section.get("topic_code"):
                            source_data = {
                                "type": "source_topic",
                                "topic_code": section.get("topic_code"),
                                "source_code": section.get("source_code") or section.get("course_code") or "",
                                "topic_name": section.get("topic_name")
                            }
                            yield f"data: {json.dumps(source_data)}\n\n"

            # ✅ suggestions
            suggestions_payload = {
                "type": "suggestions",
                "question_suggestions": (
                    node_response.question_suggestions
                )
            }

            yield (
                f"data: {json.dumps(suggestions_payload)}\n\n"
            )

            # -----------------------------
            # 🎥 STEP 4: MEDIA
            # -----------------------------
            node_meta = getattr(node_response, "metadata", None) or {}
            media = media or {}
            is_non_query_response = (
                node_meta.get("category") in {"GREETING", "GOODBYE", "THANK", "WELL_WISH", "FALLBACK", "GAP_ANALYSIS_REQUEST", "OUT_OF_SCOPE"}
                or node_meta.get("routing_reason") == "out_of_scope"
                or bool(node_meta.get("requires_upload"))
                or is_out_of_scope_text(node_response.content)
            )

            media_payload = {
                "type": "media",
                "videos": [] if is_non_query_response else media.get("videos", [])[:5],
                "images": [] if is_non_query_response else media.get("images", [])[:6],
                "pdfs": [] if is_non_query_response else media.get("pdfs", [])[:2],
                "topic_codes": [] if is_non_query_response else media.get("topic_codes", [])
            }

            yield (
                f"data: {json.dumps(media_payload)}\n\n"
            )

            company_answer = media.get("company_answer")

            if company_answer and not is_non_query_response:
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
            # 🎥 TRANSCRIPT RESULT
            # -----------------------------
            transcript_chunks = await transcript_task

            unique_chunks = []
            if not is_non_query_response:
                seen_video_ids = set()
                seen_video_titles = set()
                # Initialize seen sets with videos already delivered in media event
                for mv in (media.get("videos", []) or []):
                    m_id = str(mv.get("id") or mv.get("video_id") or mv.get("Id") or "").strip().lower()
                    m_title = str(mv.get("title") or mv.get("Title") or "").strip().lower()
                    if m_id:
                        seen_video_ids.add(m_id)
                    if m_title and len(m_title) > 3:
                        seen_video_titles.add(m_title)

                eff_transcript_q = standalone_query or user_content
                for chunk in transcript_chunks:
                    video_id = str(chunk.get("video_id") or chunk.get("id") or "").strip().lower()
                    video_url = chunk.get("video_url") or chunk.get("url") or (f"/storage/videos/{video_id}.mp4" if video_id else "")
                    video_title = chunk.get("video_title") or chunk.get("title") or "Video"
                    video_title_clean = video_title.strip().lower()
                    video_about = chunk.get("about") or chunk.get("topic_name") or ""
                    video_thumb = chunk.get("video_thumbnail") or chunk.get("thumbnail") or ""
                    video_duration = chunk.get("video_duration") or chunk.get("duration") or ""

                    # Strict relevance filtering (>= 0.70)
                    rel_score = compute_video_relevance_score({"title": video_title, "about": video_about}, eff_transcript_q)
                    if rel_score < 0.70:
                        continue

                    # Deduplication against already sent videos and within transcript
                    if video_id and video_id in seen_video_ids:
                        continue
                    if video_title_clean and len(video_title_clean) > 3 and video_title_clean in seen_video_titles:
                        continue

                    if video_id:
                        seen_video_ids.add(video_id)
                    if video_title_clean and len(video_title_clean) > 3:
                        seen_video_titles.add(video_title_clean)

                    unique_chunks.append({
                        "id": video_id,
                        "video_id": video_id,
                        "title": video_title,
                        "video_title": video_title,
                        "url": video_url,
                        "video_url": video_url,
                        "thumbnail": video_thumb,
                        "video_thumbnail": video_thumb,
                        "duration": video_duration,
                        "video_duration": video_duration,
                    })

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
            # RELATED COURSES
            # -----------------------------
            raw_codes = []
            if sections:
                for s in sections:
                    if isinstance(s, dict) and s.get("topic_code"):
                        raw_codes.append((str(s["topic_code"]).strip(), str(s.get("topic_name") or "").strip()))
            if media and isinstance(media.get("topic_codes"), list):
                for tc in media["topic_codes"]:
                    if tc:
                        raw_codes.append((str(tc).strip(), ""))

            seen_codes = set()
            valid_topic_codes = []
            for c, t_name in raw_codes:
                c_clean = c.strip()
                c_upper = c_clean.upper()
                if c_clean and c_upper not in {"COMPANY_SMS", "GAP_ANALYSIS", "NONE"} and c_clean not in seen_codes:
                    seen_codes.add(c_clean)
                    valid_topic_codes.append((c_clean, t_name))

            courses_data = []
            if not is_non_query_response and valid_topic_codes:
                for code, t_name in valid_topic_codes:
                    try:
                        res = await check_topic_course(
                            CheckTopicCourseRequest(
                                topic_code=code,
                                user_id=user_id
                            ),
                            pool=pool
                        )
                        if res and isinstance(res, dict) and res.get("data") and res["data"].get("course"):
                            if t_name and not res["data"].get("topic_name"):
                                res["data"]["topic_name"] = t_name
                            courses_data.append(res)
                    except Exception as err:
                        logger.warning(f"Error checking topic course for {code}: {err}")

            if courses_data:
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "courses",
                            "courses": courses_data,
                        }
                    )
                    + "\n\n"
                )


            # -----------------------------
            # 💾 SAVE
            # -----------------------------
            if updated_messages and isinstance(updated_messages[-1], dict) and updated_messages[-1].get("role") == "assistant":
                if is_non_query_response:
                    updated_messages[-1]["videos"] = []
                    updated_messages[-1]["images"] = []
                    updated_messages[-1]["pdfs"] = []
                    updated_messages[-1]["checkLicCoursesData"] = []
                    updated_messages[-1]["courses"] = []
                else:
                    updated_messages[-1]["images"] = list(media.get("images", [])[:6])
                    updated_messages[-1]["pdfs"] = list(media.get("pdfs", [])[:2])

                    merged_videos = list(media.get("videos", [])[:5])
                    seen_vids = {
                        str(v.get("id") or v.get("video_id") or v.get("url") or v.get("videourl") or "").strip().lower()
                        for v in merged_videos if isinstance(v, dict)
                    }
                    for uv in (unique_chunks or []):
                        k = str(uv.get("id") or uv.get("video_id") or uv.get("url") or uv.get("videourl") or "").strip().lower()
                        if k and k not in seen_vids:
                            seen_vids.add(k)
                            merged_videos.append(uv)
                    updated_messages[-1]["videos"] = merged_videos

                    if getattr(node_response, "question_suggestions", None):
                        updated_messages[-1]["question_suggestions"] = list(node_response.question_suggestions)

                    updated_messages[-1]["checkLicCoursesData"] = courses_data
                    updated_messages[-1]["courses"] = courses_data
                    updated_messages[-1]["sections"] = sections
                    updated_messages[-1]["topic_codes"] = [c for c, _ in valid_topic_codes]

            await redis_service.set_session_messages(
                session_id,
                updated_messages
            )

            print("📤 Redis updated")

            asyncio.create_task(
                session_service.update_session_messages(
                    session_id,
                    updated_messages
                )
            )

            print("💾 PostgreSQL update scheduled")

            t_stream_complete = time.perf_counter() - t_stream_start
            print(f"✅ STREAM COMPLETE (Duration: {t_stream_complete:.3f}s)")
            logger.info(
                f"\n==================== STREAM_LATENCY ====================\n"
                f"rewrite_duration={t_rew_duration:.2f}s\n"
                f"first_token_received={t_first_token[0] or 0.0:.2f}s\n"
                f"first_ui_content={t_first_ui_token[0] or 0.0:.2f}s\n"
                f"stream_complete={t_stream_complete:.2f}s\n"
                f"total={t_stream_complete:.2f}s\n"
                f"========================================================"
            )

            # Final completed & done events
            yield f"data: {json.dumps(get_status_event('completed'))}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:

            logger.exception(f"❌ STREAM ERROR: {e}")

            error_payload = {
                "type": "error",
                "message": "An error occurred while generating the response. Please try again."
            }

            yield (
                f"data: {json.dumps(error_payload)}\n\n"
            )
            yield f"data: {json.dumps(get_status_event('completed'))}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        finally:
            if 'chat_task' in locals() and not chat_task.done():
                chat_task.cancel()

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
