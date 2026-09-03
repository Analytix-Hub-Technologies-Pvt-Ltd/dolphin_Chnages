import asyncio
import json
import re
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
            print(f"Failed to fetch user from DB: {ex}")
    print(f"User details: {user_details}")

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
    print(f"User details from Redis: {user_details}")

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
                    print(f"Fallback: Loaded user details from PostgreSQL: {user_details}")
                    await redis_service.set_user_data(user_id, user_details)
        except Exception as e:
            print(f"❌ Failed to fetch user details fallback from PostgreSQL: {e}")

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

        try:

            print("✅ STREAM STARTED")

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

            last_answer = next(
                (
                    m.get("content")
                    for m in reversed(cleaned_messages)
                    if m.get("role") == "assistant"
                ),
                None
            )

            standalone_query = await chat_service.rewrite_query(
                current_query=user_content,
                previous_questions=previous_questions,
                last_answer=last_answer
            )

            # Start Understanding, Chat Pipeline, and Transcript search concurrently
            understanding_task = asyncio.create_task(
                chat_service.generate_understanding(standalone_query)
            )

            chat_task = asyncio.create_task(
                chat_service.run_chat(
                    user_id=user_id,
                    session_id=session_id,
                    db_messages=messages,
                    current_query=user_content,
                    category=payload.category,
                    user_details=user_details,
                    standalone_query=standalone_query,
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

            rewrite_text = standalone_query or ""

            for token in re.findall(r'\s+|\S+', rewrite_text):
                payload_data = {
                    "type": "rewrite_token",
                    "token": token
                }
                yield f"data: {json.dumps(payload_data)}\n\n"

            # ✅ rewrite done
            yield f"data: {json.dumps({'type': 'rewrite_done'})}\n\n"

            # -----------------------------
            # 🧠 STEP 2: UNDERSTANDING
            # -----------------------------
            understanding_summary = await understanding_task
            understanding_text = (understanding_summary or "").strip()

            # ✅ Skip EMPTY / blank responses
            if (
                understanding_text
                and understanding_text.upper() != "EMPTY"
            ):
                for token in re.findall(r'\s+|\S+', understanding_text):
                    payload_data = {
                        "type": "understanding_token",
                        "token": token
                    }
                    yield f"data: {json.dumps(payload_data)}\n\n"

                yield f"data: {json.dumps({'type': 'understanding_done'})}\n\n"

            # -----------------------------
            # 🤖 STEP 3: CHAT PIPELINE
            # -----------------------------
            (
                node_response,
                updated_messages,
                _,
                _,
                media
            ) = await chat_task

            sections = node_response.sections or []

            if sections:
                for section in sections:
                    source_data = {
                        "type": "source_topic",
                        "topic_code": section.get("topic_code"),
                        "topic_name": section.get("topic_name")
                    }
                    yield f"data: {json.dumps(source_data)}\n\n"

                    for token in re.findall(r'\s+|\S+', section.get("content", "") or ""):
                        content_data = {
                            "type": "content",
                            "token": token
                        }
                        yield f"data: {json.dumps(content_data)}\n\n"
                        await asyncio.sleep(0.0005)

            else:
                for token in re.findall(r'\s+|\S+', node_response.content or ""):
                    content_data = {
                        "type": "content",
                        "token": token
                    }
                    yield f"data: {json.dumps(content_data)}\n\n"
                    await asyncio.sleep(0.0005)


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
                or (bool(node_response.content) and "This is not part of the available course material" in node_response.content)
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

                eff_transcript_q = transcript_query or user_content
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
            # 💾 SAVE
            # -----------------------------
            if updated_messages and isinstance(updated_messages[-1], dict) and updated_messages[-1].get("role") == "assistant":
                if is_out_of_scope_response:
                    updated_messages[-1]["videos"] = []
                    updated_messages[-1]["images"] = []
                    updated_messages[-1]["pdfs"] = []
                elif unique_chunks:
                    existing_vids = updated_messages[-1].get("videos") or []
                    seen_urls = {v.get("url") or v.get("id") for v in existing_vids if isinstance(v, dict)}
                    for uv in unique_chunks:
                        k = uv.get("url") or uv.get("id")
                        if k and k not in seen_urls:
                            seen_urls.add(k)
                            existing_vids.append(uv)
                    updated_messages[-1]["videos"] = existing_vids

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

            print("✅ STREAM COMPLETE")

        except Exception as e:

            print(f"❌ STREAM ERROR: {e}")

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
