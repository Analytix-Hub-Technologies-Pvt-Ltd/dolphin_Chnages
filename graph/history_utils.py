from __future__ import annotations

from typing import Any, Dict, List


def extract_clean_history(state: Any) -> List[Dict[str, Any]]:
    """
    Extract USER + ASSISTANT messages belonging ONLY to category="QUERY".
    
    SAFETY RULES:
    - Only read:
        1. meaningful_messages
        2. meaningful_history
        3. session_messages
    - IGNORE:
        - messages  (LLM-formatted)
        - anything not dict
        - categories other than QUERY
    """

    # Step 1: Collect valid sources
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

    # Step 2: Only collect list-of-dicts
    for src in sources:
        if isinstance(src, list) and all(isinstance(x, dict) for x in src):
            merged.extend(src)

    # Step 3: Filter for QUERY & valid messages
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
    """Extract a clean list of role/content messages from graph state.

    Accepts either a dict or GraphState-like object with ``session_messages``.
    Filters out any entries missing ``role`` or ``content`` and ignores raw
    string items such as stray brackets.
    """

    messages = []
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
