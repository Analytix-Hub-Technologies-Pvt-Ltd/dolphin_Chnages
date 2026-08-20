# pipeline/router.py

from typing import Any, Dict
from loguru import logger


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


async def router_node(
    state: Dict[str, Any],
    analyzer,
) -> Dict[str, Any]:

    current_query = safe_get(state, "current_query", "")
    previous_questions = safe_get(state, "previous_questions", [])

    existing_decision = safe_get(state, "router_decision", {}) or {}

    # 🔹 Reuse decision if already exists
    if existing_decision.get("node_type") and existing_decision.get("category"):
        decision = existing_decision
    else:
        # 🔥 IMPORTANT: async call
        decision = await analyzer.classify_for_router(
            current_query,
            previous_questions
        )

    logger.info(f"[ROUTER] decision={decision}")

    # Update state
    state["router_decision"] = decision

    return state