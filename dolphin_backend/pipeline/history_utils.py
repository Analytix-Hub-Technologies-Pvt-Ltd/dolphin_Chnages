# pipeline/history_utils.py

from typing import Any, Dict, List


def extract_clean_history(state: Any) -> List[Dict[str, Any]]:
    """
    Extract USER + ASSISTANT messages ONLY for category="QUERY"
    """

    if isinstance(state, dict):
        sources = [
            state.get("meaningful_messages"),
            state.get("meaningful_history"),
            state.get("session_messages"),
        ]
    else:
        sources = [
            getattr(state, "meaningful_messages", None),
            getattr(state, "meaningful_history", None),
            getattr(state, "session_messages", None),
        ]

    merged: List[Dict[str, Any]] = []

    for src in sources:
        if isinstance(src, list) and all(isinstance(x, dict) for x in src):
            merged.extend(src)

    cleaned: List[Dict[str, Any]] = []
    seen = set()

    for msg in merged:
        role = msg.get("role") or ("assistant" if msg.get("node_type") or msg.get("type") else None)
        content = msg.get("content")
        category = (msg.get("category") or msg.get("node_type") or msg.get("type") or "").upper()

        if category != "QUERY":
            continue
        if role not in {"user", "assistant"}:
            continue
        if not content:
            continue

        key = (role, content)
        if key in seen:
            continue
        seen.add(key)

        entry = {
            "role": role,
            "content": content,
            "timestamp": msg.get("timestamp"),
            "category": category,
        }

        if role == "assistant":
            entry["video_suggestions"] = list(msg.get("video_suggestions") or [])
            entry["question_suggestions"] = list(msg.get("question_suggestions") or [])

        cleaned.append(entry)

    return cleaned


def get_clean_history(state: Any) -> List[Dict[str, Any]]:
    """Return clean role/content messages"""

    if isinstance(state, dict):
        messages = state.get("session_messages") or state.get("messages") or []
    else:
        messages = getattr(state, "session_messages", []) or getattr(state, "messages", []) or []

    clean: List[Dict[str, Any]] = []

    for msg in messages or []:
        if not isinstance(msg, dict):
            continue

        role = msg.get("role")
        content = msg.get("content")

        if role in {"user", "assistant"} and content is not None:
            clean.append(msg)

    return clean