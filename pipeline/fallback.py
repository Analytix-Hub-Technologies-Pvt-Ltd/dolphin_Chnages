# pipeline/fallback.py

from typing import Any, Dict, List
from loguru import logger


FALLBACK_PROMPT = """
You are Marine Tutor AI. A student asked a question that doesn't seem related to maritime course content.

Student Query: "{query}"

Task: Generate a VARIED, encouraging response that:
1. Politely acknowledges their question
2. Suggest maritime topics
3. Encourage learning
4. Keep it short (2-3 sentences)
5. Be warm

Generate a UNIQUE response:
"""


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


# 🔹 Dynamic fallback generator (same as before)
async def generate_dynamic_fallback(query: str, openai_service=None, is_social: bool = False) -> str:
    if not is_social:
        return "This is not part of the available course material. Please ask a question related to the Marine/Maritime course content."

    if not openai_service:
        import random
        messages = [
            f"Thanks for your question about '{query}'! I specialize in maritime education. What marine topic would you like to explore?",
            f"That's an interesting query! My focus is on maritime course content. What would you like to learn?",
            f"I appreciate your question! I can help with navigation, ship safety, and marine systems.",
        ]
        return random.choice(messages)

    try:
        prompt = FALLBACK_PROMPT.format(query=query)

        response = await openai_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            category="FALLBACK",
        )
        return response.strip()

    except Exception as e:
        logger.error(f"[FALLBACK] LLM failed: {e}")
        return f"I'd love to help! While '{query}' isn't maritime-related, I can assist with marine topics."


# 🔹 MAIN FUNCTION (replaces class)
async def fallback_node(
    state: Dict[str, Any],
    suggestion_service,
    openai_service=None,
) -> Dict[str, Any]:

    # decision = safe_get(state, "router_decision", {})
    decision: Dict[str, Any] = safe_get(state, "router_decision", {}) or {}
    query = safe_get(state, "current_query", "")
    chunks: List[Dict[str, Any]] = safe_get(state, "retrieval_chunks", []) or []
    previous_questions: List[str] = safe_get(state, "previous_questions", []) or []
    messages: List[Dict[str, Any]] = safe_get(state, "messages", []) or []

    combined_query = " ".join(q for q in [query] + previous_questions if q)

    node_type = decision.get("node_type", "").lower()
    is_social = node_type in {"greeting", "goodbye", "thank", "well_wish"}
    query_lower = (query or combined_query).lower().strip().rstrip("?.!")
    social_words = {"hello", "hi", "hey", "good morning", "good evening", "how are you", "thank you", "thanks"}
    if any(word in query_lower for word in social_words) or len(query_lower) < 3:
        is_social = True

    # 🔹 Generate fallback response
    content = await generate_dynamic_fallback(query or combined_query, openai_service, is_social=is_social)

    category = decision.get("category") or "FALLBACK"

    # 🔹 Suggestions (same logic)
    dynamic_suggestions = suggestion_service.generate(
        query=combined_query,
        chunks=chunks,
        history=messages,
        short_topic=decision.get("short_topic", "marine topic"),
        category=category,
    )

    # 🔹 Build response (same structure as BaseNode)
    state["node_response"] = {
        "type": "fallback",
        "content": content,
        "chunks_used": chunks,
        "video_suggestions": [],
        "videos": [],
        "images": [],
        "pdfs": [],
        "question_suggestions": dynamic_suggestions,
        "metadata": {
            "short_topic": decision.get("short_topic", "marine"),
            "routing_reason": decision.get("reason", "fallback"),
        },
    }

    return state