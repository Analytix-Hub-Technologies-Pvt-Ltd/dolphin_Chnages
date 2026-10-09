# pipeline/greeting.py

from typing import Any, Dict, List
from loguru import logger


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


async def greeting_node(state: Dict[str, Any]) -> Dict[str, Any]:

    decision = safe_get(state, "router_decision", {}) or {}
    user_profile = safe_get(state, "user_profile", {}) or {}

    user_name = decision.get("user_name") or user_profile.get("name")

    # 🔹 Content
    if user_name:
        content = (
            f"Hello {user_name}!\n\n"
            f"Welcome to Dolphin AI. I am your maritime AI assistant, ready to assist you with maritime education, "
            f"vessel operations, navigation, marine engineering, safety regulations, and your company's SMS procedures.\n\n"
            f"How can I assist you today?"
        )
    else:
        content = (
            "Hello!\n\n"
            "Welcome to Dolphin AI. I am your maritime AI assistant, ready to assist you with maritime education, "
            "vessel operations, navigation, marine engineering, safety regulations, and your company's SMS procedures.\n\n"
            "How can I assist you today?"
        )

    dynamic_suggestions = [
        "What are the different types of merchant ships?",
        "What is the procedure for enclosed space entry?",
        "Explain COLREG Rule 15 crossing situation",
    ]

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
            "category": "GREETING",
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