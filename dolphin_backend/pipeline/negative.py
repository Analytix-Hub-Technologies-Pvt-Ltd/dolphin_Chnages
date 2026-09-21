# pipeline/negative.py

from typing import Any, Dict, List


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


async def negative_node(
    state: Dict[str, Any],
    suggestion_service=None,  # kept for compatibility (not used)
) -> Dict[str, Any]:

    decision = safe_get(state, "router_decision", {}) or {}
    chunks: List[Dict[str, Any]] = safe_get(state, "retrieval_chunks", []) or []
    query = safe_get(state, "current_query", "") or ""
    previous_questions: List[str] = safe_get(state, "previous_questions", []) or []
    messages = safe_get(state, "messages", [])

    combined_query = " ".join(q for q in [query] + previous_questions if q)

    user_name = decision.get("user_name")

    # 🔹 Check if misclassified workplace safety query
    if chunks and len(chunks) > 0:

        query_lower = query.lower()

        workplace_safety_keywords = [
            "harassment", "harassing", "harassed",
            "bullying", "bullied",
            "intoxicated", "intoxication",
            "crew member", "crew management",
            "workplace", "incident",
            "advice", "how should", "what should",
            "how to handle", "what do i do"
        ]

        if any(kw in query_lower for kw in workplace_safety_keywords):

            # ✅ Helpful correction instead of negative response
            content = (
                "I understand you're asking about a workplace situation. "
                "Let me help you find relevant information about crew management and safety procedures.\n\n"
                "Please rephrase your question like:\n"
                "- What are the procedures for handling crew misconduct?\n"
                "- How should harassment be reported?\n"
                "- What are safety protocols for intoxicated crew members?"
            )

        else:
            # Standard negative
            content = (
                "## I'm sorry this didn't feel helpful to you.\n"
                "Please tell me what you'd like explained differently."
            )

    else:
        # No chunks → normal negative
        content = (
            "## I'm sorry this didn't feel helpful to you.\n"
            "Please tell me what you'd like explained differently."
        )

    # 🔹 Build response
    state["node_response"] = {
        "type": "negative",
        "content": content,
        "chunks_used": [],
        "video_suggestions": [],
        "videos": [],
        "images": [],
        "pdfs": [],
        "question_suggestions": [],
        "metadata": {
            "short_topic": "negative",
            "routing_reason": decision.get("reason", "negative"),
        },
    }

    return state