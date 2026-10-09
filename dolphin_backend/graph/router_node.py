from __future__ import annotations
from typing import Any, Dict
from loguru import logger

from graph.base_node import BaseNode
from services.query_analyzer import EnhancedQueryAnalyzer


class RouterNode(BaseNode):
    def __init__(self, analyzer: EnhancedQueryAnalyzer) -> None:
        super().__init__("router")
        self.analyzer = analyzer

    # Safe accessor for both dict and GraphState
    def _safe_get(self, state: Any, key: str, default=None):
        if isinstance(state, dict):
            return state.get(key, default)
        return getattr(state, key, default)

    async def run(self, state: Any) -> Dict[str, Any]:

        # 🔥 MUST use safe_get (GraphState does NOT support .get)
        current_query = self._safe_get(state, "current_query", "")
        previous_questions = self._safe_get(state, "previous_questions", [])

        existing_decision = self._safe_get(state, "router_decision", {}) or {}
        if existing_decision.get("node_type") and existing_decision.get("category"):
            decision = existing_decision
        else:
            # ⚡ FIX: classify_for_router is async — must await it
            decision = await self.analyzer.classify_for_router(
                current_query,
                previous_questions
            )

        logger.info("Routing decision", decision=decision)

        # MUST return both fields (dicts)
        return {
            "router_decision": decision,
            "node_response": {}
        }
