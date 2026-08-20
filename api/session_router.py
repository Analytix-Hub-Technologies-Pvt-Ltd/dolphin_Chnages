from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from datetime import datetime
import json

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from api.dependencies import get_db_pool
from services.session_service import SessionService


class SessionCreateRequest(BaseModel):
    title: Optional[str] = None
    user_id: Optional[str] = None


class SessionSummary(BaseModel):
    session_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int
    is_saved: bool = False
    last_message: Optional[Dict[str, Any]] = None


class SessionDetail(SessionSummary):
    messages: List[Dict[str, Any]]

class MessageLikeRequest(BaseModel):
    session_id: str
    message_id: int
    like: Optional[int] = None
    user_id: str
    commond: Optional[str] = None

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _normalize_category(raw_value: Any, default: str = "QUERY") -> str:
    allowed = {"GREETING", "QUERY", "QUIZ", "SUMMARY", "FALLBACK"}
    if isinstance(raw_value, str):
        candidate = raw_value.strip().upper()
        if candidate in allowed:
            return candidate
    return default


def _clean_messages(msgs: Any) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for msg in msgs or []:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        category = _normalize_category(msg.get("category") or msg.get("node_type") or msg.get("type"), "QUERY")
        timestamp = msg.get("timestamp")
        command = msg.get("command")

        if role in {"user", "assistant"} and content is not None:
            normalized = {
                "message_id": msg.get("message_id"),
                "role": role,
                "content": content,
                "timestamp": timestamp,
                "category": category,
                "like": msg.get("like"),
                "command": command
            }
            if role == "assistant":
                normalized["video_suggestions"] = list(msg.get("video_suggestions") or [])
                normalized["question_suggestions"] = list(msg.get("question_suggestions") or [])
                normalized["like"] = msg.get("like")
                normalized["command"] = msg.get("command")
            cleaned.append(normalized)
            continue
        

        if "question" in msg:
            question = str(msg.get("question") or "").strip()
            if question:
                cleaned.append(
                    {
                        "role": "user",
                        "content": question,
                        "timestamp": timestamp,
                        "category": category,
                    }
                )
            continue

        if "response" in msg:
            response_text = str(msg.get("response") or "").strip()
            if response_text:
                cleaned.append(
                    {
                        "role": "assistant",
                        "content": response_text,
                        "timestamp": timestamp,
                        "category": category,
                        "video_suggestions": list(msg.get("video_suggestions") or []),
                        "question_suggestions": list(msg.get("question_suggestions") or []),
                    }
                )
    return cleaned

def _build_summary(session: Dict[str, Any]) -> Dict[str, Any]:
    messages = session.get("messages") if isinstance(session, dict) else None
    last_message = session.get("last_message") if isinstance(session, dict) else None
    message_count = session.get("message_count") if isinstance(session, dict) else 0
    is_saved = session.get("is_saved", False) if isinstance(session, dict) else False

    if isinstance(last_message, str):
        try:
            last_message = json.loads(last_message)
        except json.JSONDecodeError:
            last_message = None

    if isinstance(messages, str):
        try:
            messages = json.loads(messages)
        except json.JSONDecodeError:
            messages = []

    if isinstance(messages, list):
        normalized_messages: List[Dict[str, Any]] = []

        for message in messages:
            if isinstance(message, str):
                try:
                    message = json.loads(message)
                except json.JSONDecodeError:
                    message = None

            if isinstance(message, dict):
                normalized_messages.append(message)

        messages = _clean_messages(normalized_messages)

    if isinstance(messages, list):
        message_count = len(messages)
        last_message = messages[-1] if messages else None

    return {
        "session_id": session.get("session_id"),
        "title": session.get("title"),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
        "is_saved": is_saved,   # added response field
        "message_count": message_count or 0,
        "last_message": last_message,
        "messages": messages or [],
    }

@router.get("", response_model=List[SessionSummary])
async def list_sessions(user_id: str,search: Optional[str] = None,pool: Pool = Depends(get_db_pool)):
    session_service = SessionService(pool)
    sessions = await session_service.list_sessions(user_id, search)
    return [_build_summary(session) for session in sessions]

@router.post("", response_model=SessionSummary)
async def create_session(
    payload: SessionCreateRequest,
    request: Request,
    pool: Pool = Depends(get_db_pool),
):
    if not payload.user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    user_id = payload.user_id

    print("Creating session for:", user_id)

    session_service = SessionService(pool)
    session = await session_service.create_session(user_id, payload.title)

    return _build_summary(session)

@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    user_id: str,
    pool: Pool = Depends(get_db_pool),
):
    session_service = SessionService(pool)
    session = await session_service.get_session(session_id, user_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    summary = _build_summary(session)
    summary["messages"] = summary.get("messages", [])

    if not summary["messages"]:
        messages = session.get("messages") if isinstance(session, dict) else []
        summary["messages"] = messages if isinstance(messages, list) else []

    return summary

@router.post("/save/{session_id}")
async def toggle_save_session(
    session_id: str,
    pool: Pool = Depends(get_db_pool),
):
    print("Toggle save session:", session_id)

    session_service = SessionService(pool)
    session = await session_service.toggle_save_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    return {
        "message": "Session save status updated successfully",
        "session_id": session_id,
        "is_saved": session["is_saved"]
    }


@router.get("/saved/{user_id}")
async def get_saved_sessions(
    user_id: str,
    pool: Pool = Depends(get_db_pool),
):
    print("Fetching saved sessions for:", user_id)

    session_service = SessionService(pool)
    sessions = await session_service.get_saved_sessions(user_id)

    return {
        "user_id": user_id,
        "saved_sessions": sessions
    }

@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    pool: Pool = Depends(get_db_pool),
):
    print("🗑 Deleting session:", session_id)

    session_service = SessionService(pool)
    deleted = await session_service.delete_session(session_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    return {
        "message": "Session deleted successfully",
        "session_id": session_id
    }

@router.post("/message-feedback")
async def message_feedback(
    payload: MessageLikeRequest,
    pool: Pool = Depends(get_db_pool)
):
    session_service = SessionService(pool)

    session = await session_service.get_session(
        payload.session_id,
        payload.user_id
    )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    messages = session.get("messages", [])

    # Convert JSON string -> Python list
    if isinstance(messages, str):
        try:
            messages = json.loads(messages)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=500,
                detail="Invalid messages format"
            )

    updated = False

    for msg in messages:

        if not isinstance(msg, dict):
            continue

        if (
            msg.get("role") == "assistant"
            and msg.get("message_id") == payload.message_id
        ):
            msg["like"] = payload.like
            msg["command"] = payload.commond
            updated = True
            break

    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"Assistant message {payload.message_id} not found"
        )

    await session_service.update_session_messages(
        payload.session_id,
        messages
    )

    return {
        "success": True,
        "message_id": payload.message_id,
        "like": payload.like,
        "command": payload.commond
    }


@router.get("/topic/{topic_code}")
async def get_topic_content(
    topic_code: str,
    pool: Pool = Depends(get_db_pool),
):
    query = """
        SELECT
            cc.course_code,
            mc.course_name,
            cc.topic_name,
            cc.topic_content
        FROM course_content cc
        LEFT JOIN master_course_data mc
            ON cc.course_code = mc.course_code
        WHERE cc.topic_code = $1
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, topic_code)

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Topic not found"
        )

    return dict(row)


class SessionListResponse(BaseModel):
    id: str | None = None
    username: str | None = None
    chat_title: str | None = None
    time: datetime | None = None
    session_id: str



@router.get("/get_all/sessions/", response_model=list[SessionListResponse])
async def get_all_sessions(
    pool: Pool = Depends(get_db_pool),
):
    session_service = SessionService(pool)

    return await session_service.get_all_sessions()


class SessionListResponse(BaseModel):
    id: str
    username: str
    chat_title: str | None = None
    time: datetime | None = None
    session_id: str

class PaginatedSessionResponse(BaseModel):
    total: int
    limit: int
    offset: int
    data: list[SessionListResponse]

@router.get("/", response_model=PaginatedSessionResponse)
async def get_all_sessions_filter(
    session_date: Optional[date] = Query(
        default=None,
        description="Filter by session date (YYYY-MM-DD)",
    ),
    student_name: Optional[str] = Query(
        default=None,
        description="Filter by student name",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Number of records to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of records to skip",
    ),
    pool: Pool = Depends(get_db_pool),
):
    session_service = SessionService(pool)

    return await session_service.get_all_sessions_filter(
        session_date=session_date,
        student_name=student_name,
        limit=limit,
        offset=offset,
    )

# @router.get("/", response_model=list[SessionListResponse])
# async def get_all_sessions_filter(
#     session_date: Optional[date] = Query(
#         default=None,
#         description="Filter by session date (YYYY-MM-DD)",
#     ),
#     student_name: Optional[str] = Query(
#         default=None,
#         description="Filter by student name",
#     ),
#     pool: Pool = Depends(get_db_pool),
# ):
#     session_service = SessionService(pool)

#     return await session_service.get_all_sessions_filter(
#         session_date=session_date,
#         student_name=student_name,
#     )