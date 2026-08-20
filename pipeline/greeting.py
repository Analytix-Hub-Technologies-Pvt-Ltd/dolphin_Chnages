# pipeline/greeting.py

from typing import Any, Dict, List
from loguru import logger


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


async def greeting_node(state: Dict[str, Any]) -> Dict[str, Any]:

    decision = safe_get(state, "router_decision", {}) or {}

    query = safe_get(state, "current_query", "")
    previous_questions: List[str] = safe_get(state, "previous_questions", []) or []
    messages = safe_get(state, "messages", [])

    combined_query = " ".join(q for q in [query] + previous_questions if q)

    user_name = decision.get("user_name")

    # 🔹 Content
    if user_name:
        content = (
            f"## 👋 Hello {user_name}!\n"
            f"Welcome to Marine Tutor AI.\n"
            f"I'm here to help you explore marine topics, summaries, quizzes"
        )
    else:
        content = (
            "## 👋 Welcome to Marine Tutor AI\n"
            "Hello! I'm here to help you explore marine science topics, summaries, quizzes"
        )

    # 🔹 No suggestions (same logic)
    dynamic_suggestions = []

    # 🔹 Build response (NO media)
    response = {
        "type": "greeting",
        "content": content,
        "chunks_used": [],
        "video_suggestions": [],
        "videos": [],
        "images": [],
        "pdfs": [],
        "question_suggestions": dynamic_suggestions,
        "metadata": {
            "short_topic": decision.get("short_topic", "greeting"),
            "routing_reason": decision.get("reason", "greeting"),
        },
    }

    # 🔴 SAFETY CHECK
    if response.get("video_suggestions") or response.get("videos"):
        logger.error("[GREETING] BUG: Videos leaked! Removing them.")
        response["video_suggestions"] = []
        response["videos"] = []
        if "metadata" in response:
            response["metadata"]["video_suggestions"] = []
            response["metadata"]["videos"] = []

    state["node_response"] = response

    return state