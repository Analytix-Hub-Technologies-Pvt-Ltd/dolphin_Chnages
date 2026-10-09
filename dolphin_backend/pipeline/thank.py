# pipeline/thank.py

from typing import Any, Dict
from loguru import logger


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


async def thank_node(state: Dict[str, Any]) -> Dict[str, Any]:

    decision = safe_get(state, "router_decision", {}) or {}
    query = safe_get(state, "current_query", "")
    previous_questions = safe_get(state, "previous_questions", [])

    user_name = decision.get("user_name")

    if user_name:
        content = f"## Thank you {user_name}!\nI'm glad you found the course helpful."
    else:
        content = "## Thank you!\nI'm glad you found the course helpful."

    response = {
        "type": "thank_you",
        "content": content,
        "chunks_used": [],
        "video_suggestions": [],
        "videos": [],
        "images": [],
        "pdfs": [],
        "question_suggestions": [],
        "metadata": {
            "short_topic": "thank_you",
            "routing_reason": decision.get("reason", "User expressed thanks"),
        },
    }

    # 🔴 SAFETY CHECK
    if response.get("video_suggestions") or response.get("videos"):
        logger.error("[THANK] BUG: Videos leaked! Removing them.")
        response["video_suggestions"] = []
        response["videos"] = []

    state["node_response"] = response
    return state