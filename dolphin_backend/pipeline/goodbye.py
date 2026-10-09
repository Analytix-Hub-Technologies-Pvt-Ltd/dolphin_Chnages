# pipeline/goodbye.py

from typing import Any, Dict, List
from loguru import logger


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


async def goodbye_node(state: Dict[str, Any]) -> Dict[str, Any]:

    decision = safe_get(state, "router_decision", {}) or {}

    query = safe_get(state, "current_query", "")
    previous_questions: List[str] = safe_get(state, "previous_questions", []) or []
    messages = safe_get(state, "messages", [])

    combined_query = " ".join(q for q in [query] + previous_questions if q)

    user_name = decision.get("user_name")

    # 🔹 Content generation
    if user_name:
        content = (
            f"## 👋 Goodbye {user_name}!\n"
            "Thank you for using Marine Tutor AI.\n"
            "Have a great day and sail safe! ⚓"
        )
    else:
        content = (
            "## 👋 Goodbye!\n"
            "Thank you for using Marine Tutor AI.\n"
            "Hope to see you again soon! ⚓"
        )

    # 🔹 No suggestions for goodbye
    dynamic_suggestions = []

    # 🔹 Build response (NO media)
    response = {
        "type": "goodbye",
        "content": content,
        "chunks_used": [],  # 🚨 important
        "video_suggestions": [],
        "videos": [],
        "images": [],
        "pdfs": [],
        "question_suggestions": dynamic_suggestions,
        "metadata": {
            "short_topic": "goodbye",
            "routing_reason": decision.get("reason", "goodbye"),
        },
    }

    # 🔴 SAFETY CHECK (same as original)
    if response.get("video_suggestions") or response.get("videos"):
        logger.error("[GOODBYE] BUG: Videos leaked! Removing them.")
        response["video_suggestions"] = []
        response["videos"] = []
        if "metadata" in response:
            response["metadata"]["video_suggestions"] = []
            response["metadata"]["videos"] = []

    state["node_response"] = response

    return state