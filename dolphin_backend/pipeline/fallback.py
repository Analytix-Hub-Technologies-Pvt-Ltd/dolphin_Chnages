# pipeline/fallback.py

from typing import Any, Dict, List
from loguru import logger


FALLBACK_PROMPT = """
You are Marine Tutor AI, specialized exclusively in maritime education, navigation, marine engineering, ship operations, safety regulations, and seafarer training.

User Query: "{query}"

Task: Generate a clear, polite response stating that:
1. You are Marine Tutor AI and assist only with maritime, nautical science, marine engineering, and vessel operations topics.
2. This topic is outside the marine training curriculum.
3. Invite the user to ask questions related to maritime and shipboard operations (e.g., COLREGS, marine diesel engines, firefighting, navigation, or port state control).
4. Strictly do NOT answer the non-marine query and do NOT provide general knowledge or code for it.
5. Keep it concise (2-3 sentences), professional, and without markdown code blocks.
"""


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


# 🔹 Dynamic fallback generator
async def generate_dynamic_fallback(query: str, openai_service=None) -> tuple[str, list[str]]:
    try:
        from services.off_topic_detector import generate_dynamic_off_topic_response
        text, suggs = await generate_dynamic_off_topic_response(query)
        if text:
            return text, suggs
    except Exception as e:
        logger.debug(f"[FALLBACK] Dynamic generator error: {e}")

    try:
        from services.off_topic_detector import get_varied_off_topic_response
        text, suggs = get_varied_off_topic_response(query)
        return text, suggs
    except Exception:
        return (
            "I am Marine Tutor AI, specialized exclusively in maritime education, navigation, "
            "marine engineering, ship operations, safety regulations, and seafarer training.\n\n"
            "This topic is outside the marine training curriculum. Please ask questions related to "
            "maritime and shipboard operations (e.g., COLREGS, marine diesel engines, firefighting, navigation, or port state control).",
            [
                "What is anchor watch procedure?",
                "Explain COLREG Rule 15 crossing situation",
                "What are the checks for marine auxiliary boiler?"
            ]
        )


# 🔹 MAIN FUNCTION
async def fallback_node(
    state: Dict[str, Any],
    suggestion_service,
    openai_service=None,
) -> Dict[str, Any]:

    decision: Dict[str, Any] = safe_get(state, "router_decision", {}) or {}
    query = safe_get(state, "current_query", "")
    previous_questions: List[str] = safe_get(state, "previous_questions", []) or []

    combined_query = " ".join(q for q in [query] + previous_questions if q)

    # 🔹 Generate fallback response
    content, dynamic_suggs = await generate_dynamic_fallback(query or combined_query, openai_service)
    import re
    content = re.sub(r'^(?:#{1,6}\s*)?(?:Out of Scope|Off Topic)[:\s]*\n*', '', content, flags=re.IGNORECASE).strip()

    marine_suggestions = dynamic_suggs or [
        "What is anchor watch procedure?",
        "Explain COLREG Rule 15 crossing situation",
        "What are the checks for marine auxiliary boiler?"
    ]

    # 🔹 Stream response if streaming is active
    stream_callback = safe_get(state, "stream_callback")
    if stream_callback:
        try:
            tokens = re.findall(r'\S+\s*|\n+', content)
            for tok in tokens:
                await stream_callback({"type": "content", "token": tok})
            state["_streamed_live"] = True
        except Exception as e:
            logger.warning(f"Failed streaming fallback response: {e}")

    # 🔹 Clear any retrieval chunks and videos from state
    state["retrieval_chunks"] = []
    state["video_suggestions"] = []
    state["company_answer"] = None

    # 🔹 Build response
    state["node_response"] = {
        "type": "query",
        "content": content,
        "sections": [
            {
                "topic_code": "",
                "topic_name": "",
                "content": content,
            }
        ],
        "chunks_used": [],
        "video_suggestions": [],
        "videos": [],
        "images": [],
        "pdfs": [],
        "question_suggestions": marine_suggestions,
        "metadata": {
            "short_topic": "marine",
            "routing_reason": decision.get("reason", "off_topic"),
            "out_of_scope": True,
        },
    }

    return state