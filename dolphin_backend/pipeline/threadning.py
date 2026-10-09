# pipeline/threadning.py

from typing import Any, Dict


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


async def threadning_node(state: Dict[str, Any]) -> Dict[str, Any]:

    decision = safe_get(state, "router_decision", {}) or {}

    user_name = decision.get("user_name")

    if user_name:
        content = (
            "## Let’s keep the conversation respectful and focused on learning.\n"
            "How can I help you with the course content?\n"
        )
    else:
        content = (
            "## Let’s keep the conversation respectful and focused on learning.\n"
            "How can I help you with the course content?\n"
        )

    state["node_response"] = {
        "type": "threadning",
        "content": content,
        "chunks_used": [],
        "video_suggestions": [],
        "videos": [],
        "images": [],
        "pdfs": [],
        "question_suggestions": [],
        "metadata": {
            "short_topic": "threadning",
            "routing_reason": decision.get("reason", "threadning"),
        },
    }

    return state