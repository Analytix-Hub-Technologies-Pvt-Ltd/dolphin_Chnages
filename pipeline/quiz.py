# pipeline/quiz.py

import json
import re
from typing import Any, Dict, List
from loguru import logger

from pipeline.history_utils import extract_clean_history


# -----------------------------
# HELPERS
# -----------------------------
def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9]*", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


# -----------------------------
# MEDIA AGGREGATION
# -----------------------------
def aggregate_media(chunks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    seen_ids = set()

    def dedupe(items):
        result = []
        for item in items or []:
            identifier = None
            if isinstance(item, dict):
                identifier = str(item.get("Id") or item.get("id") or item.get("ID") or "")
            if identifier and identifier in seen_ids:
                continue
            if identifier:
                seen_ids.add(identifier)
            result.append(item)
        return result

    videos, images, pdfs = [], [], []

    for chunk in chunks:
        videos.extend(chunk.get("videos", []) or [])
        images.extend(chunk.get("images", []) or [])
        pdfs.extend(chunk.get("pdfs", []) or [])

    return {
        "videos": dedupe(videos),
        "images": dedupe(images),
        "pdfs": dedupe(pdfs),
    }


# -----------------------------
# CONVERSATION CONTENT
# -----------------------------
def extract_conversation_content(history):
    content = []

    for msg in history[-10:]:
        if msg.get("role") == "assistant":
            if isinstance(msg.get("content"), str):
                content.append(msg["content"])

    return "\n\n---\n\n".join(content)


# -----------------------------
# MAIN FUNCTION
# -----------------------------
async def quiz_node(
    state: Dict[str, Any],
    openai_service,
    suggestion_service,
) -> Dict[str, Any]:

    decision = safe_get(state, "router_decision", {}) or {}
    chunks = safe_get(state, "retrieval_chunks", []) or []
    query = safe_get(state, "current_query", "") or ""
    resolved_topic = safe_get(state, "resolved_quiz_topic", "") or query

    history = extract_clean_history(state)

    media_bundle = aggregate_media(chunks)

    query_lower = query.lower()

    is_generic = query_lower in [
        "quiz", "mcq", "test", "practice test",
        "give me a quiz", "generate quiz", "quiz me"
    ]

    # -----------------------------
    # CONTENT SOURCE
    # -----------------------------
    if is_generic and history:
        content_body = extract_conversation_content(history)
    else:
        content_body = "\n\n---\n\n".join(
            (c.get("content") or "") for c in chunks
        )

    # -----------------------------
    # EMPTY CONTENT FALLBACK
    # -----------------------------
    if not content_body or len(content_body) < 100:
        quiz_items = [{
            "question": "Not enough content to generate quiz.",
            "options": ["Ask topic", "Explain safety", "Show topics", "Help"],
            "correct_index": 0
        }]

        state["node_response"] = {
            "type": "quiz",
            "content": {
                "type": "quiz",
                "quiz_items": quiz_items,
                "content": "Insufficient content"
            },
            "chunks_used": [],
            "video_suggestions": [],
            "videos": [],
            "images": [],
            "pdfs": [],
            "question_suggestions": [],
            "metadata": {
                "short_topic": resolved_topic,
                "routing_reason": "insufficient_content",
            },
        }

        return state

    # -----------------------------
    # PROMPT
    # -----------------------------
    prompt = f"""
Create 5 MCQ quiz in JSON.

CONTENT:
{content_body}

FORMAT:
{{
 "quiz_items": [
   {{"question": "", "options": ["","","",""], "correct_index": 0}}
 ]
}}
"""

    # -----------------------------
    # LLM CALL
    # -----------------------------
    raw = await openai_service.chat(
        [{"role": "user", "content": prompt}],
        category="QUIZ"
    )

    quiz_text = strip_code_fences(raw)

    # -----------------------------
    # PARSE
    # -----------------------------
    try:
        parsed = json.loads(quiz_text)
        quiz_items = parsed.get("quiz_items", [])

        if not quiz_items:
            raise ValueError()

    except Exception:
        logger.error("[QUIZ] parse failed")

        quiz_items = [{
            "question": "Quiz generation failed",
            "options": ["Try again", "Ask topic", "Learn", "Exit"],
            "correct_index": 0
        }]

    # -----------------------------
    # FINAL RESPONSE
    # -----------------------------
    state["node_response"] = {
        "type": "quiz",
        "content": {
            "type": "quiz",
            "quiz_items": quiz_items,
            "content": f"Quiz on {resolved_topic}"
        },
        "chunks_used": chunks,
        "video_suggestions": [],
        "videos": [],
        "images": [],
        "pdfs": [],
        "question_suggestions": suggestion_service.generate(
            query=query,
            chunks=chunks,
            history=history,
            short_topic=resolved_topic,
            category="quiz",
        ),
        "metadata": {
            "short_topic": resolved_topic,
            "routing_reason": decision.get("reason", "quiz"),
        },
    }

    return state