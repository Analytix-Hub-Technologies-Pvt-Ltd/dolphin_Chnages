"""Utility script to normalize chat_sessions.messages to the canonical schema."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List

import asyncpg
from config import settings

ALLOWED_CATEGORIES = {"GREETING", "QUERY", "QUIZ", "SUMMARY", "FALLBACK"}


def _normalize_category(raw_value: Any, default: str = "QUERY") -> str:
    if isinstance(raw_value, str):
        candidate = raw_value.strip().upper()
        if candidate in ALLOWED_CATEGORIES:
            return candidate
    return default


def _clean_messages(db_messages: List[Any]) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for raw in db_messages or []:
        if not isinstance(raw, dict):
            continue

        role = raw.get("role")
        content = raw.get("content")
        category = _normalize_category(raw.get("category") or raw.get("node_type") or raw.get("type"))
        timestamp = raw.get("timestamp") or datetime.utcnow().isoformat()

        if role in {"user", "assistant"} and content is not None:
            entry = {
                "role": role,
                "content": str(content),
                "timestamp": timestamp,
                "category": category,
            }
            if role == "assistant":
                entry["video_suggestions"] = list(raw.get("video_suggestions") or [])
                entry["question_suggestions"] = list(raw.get("question_suggestions") or [])
            cleaned.append(entry)
            continue

        if "question" in raw:
            question = str(raw.get("question") or "").strip()
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

        if "response" in raw:
            response_text = str(raw.get("response") or "").strip()
            if response_text:
                cleaned.append(
                    {
                        "role": "assistant",
                        "content": response_text,
                        "timestamp": timestamp,
                        "category": category,
                        "video_suggestions": list(raw.get("video_suggestions") or []),
                        "question_suggestions": list(raw.get("question_suggestions") or []),
                    }
                )
    return cleaned


async def main() -> None:
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )
    rows = await conn.fetch("SELECT session_id, messages FROM chat_sessions")
    for row in rows:
        session_id = row["session_id"]
        messages = row.get("messages") or []
        cleaned = _clean_messages(messages if isinstance(messages, list) else [])
        await conn.execute(
            "UPDATE chat_sessions SET messages=$1::jsonb WHERE session_id=$2",
            cleaned,
            session_id,
        )
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())