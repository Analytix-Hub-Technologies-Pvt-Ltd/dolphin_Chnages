# pipeline/well_wish.py

from typing import Any, Dict
from loguru import logger


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


async def well_wish_node(state: Dict[str, Any]) -> Dict[str, Any]:

    decision = safe_get(state, "router_decision", {}) or {}

    user_name = decision.get("user_name")

    if user_name:
        content = (
            "## I'm doing well, thank you!\n"
            "How can I assist you with the marine course today?\n"
        )
    else:
        content = (
            "## I'm doing well, thank you!\n"
            "How can I assist you with the marine course today?\n"
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