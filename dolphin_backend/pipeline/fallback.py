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
async def generate_dynamic_fallback(query: str, openai_service=None) -> str:

    default_msg = (
        "I am Marine Tutor AI, specialized exclusively in maritime education, navigation, "
        "marine engineering, ship operations, safety regulations, and seafarer training.\n\n"
        "This topic is outside the marine training curriculum. Please ask questions related to "
        "maritime and shipboard operations (e.g., COLREGS, marine diesel engines, firefighting, navigation, or port state control)."
    )

    if not openai_service:
        return default_msg

    try:
        prompt = FALLBACK_PROMPT.format(query=query)

        response = await openai_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            category="FALLBACK",
        )
        res_text = response.strip()
        return res_text if res_text else default_msg

    except Exception as e:
        logger.error(f"[FALLBACK] LLM failed: {e}")
        return default_msg


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
    content = await generate_dynamic_fallback(query or combined_query, openai_service)
    import re
    content = re.sub(r'^(?:#{1,6}\s*)?(?:Out of Scope|Off Topic)[:\s]*\n*', '', content, flags=re.IGNORECASE).strip()

    marine_suggestions = [
        "What is anchor watch procedure?",
        "Explain COLREG Rule 15 crossing situation",
        "What are the checks for marine auxiliary boiler?"
    ]

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