# pipeline/well_wish.py

from typing import Any, Dict
from loguru import logger


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


async def well_wish_node(state: Dict[str, Any]) -> Dict[str, Any]:

    decision = safe_get(state, "router_decision", {}) or {}

    user_profile = safe_get(state, "user_profile", {}) or {}
    user_name = decision.get("user_name") or user_profile.get("user_name") or user_profile.get("name")

    if user_name:
        content = (
            f"Hello {user_name}! I'm doing well, thank you for asking.\n\n"
            "How can I assist you with your maritime course lessons, operations, or company SMS procedures today?"
        )
    else:
        content = (
            "I'm doing well, thank you for asking!\n\n"
            "How can I assist you with your maritime course lessons, operations, or company SMS procedures today?"
        )

    response = {
        "type": "well_wish",
        "content": content,
        "chunks_used": [],
        "video_suggestions": [],
        "videos": [],
        "images": [],
        "pdfs": [],
        "question_suggestions": [],
        "metadata": {
            "category": "WELL_WISH",
            "short_topic": "well_wish",
            "routing_reason": decision.get("reason", "well_wish"),
        },
    }

    # 🔴 SAFETY CHECK
    if response.get("video_suggestions") or response.get("videos"):
        logger.error("[WELL_WISH] BUG: Videos leaked! Removing them.")
        response["video_suggestions"] = []
        response["videos"] = []

    state["node_response"] = response
    return state