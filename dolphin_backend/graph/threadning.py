from __future__ import annotations

from typing import Any, Dict, List
from graph.base_node import BaseNode
from services.suggestion_service import SuggestionService


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


class ThreadningNode(BaseNode):
    def __init__(self, suggestion_service: SuggestionService) -> None:
        super().__init__("threadning")
        self.suggestion_service = suggestion_service

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:

        decision = safe_get(state, "router_decision", {})
        chunks: List[Dict[str, Any]] = safe_get(state, "retrieval_chunks", [])
        query = safe_get(state, "current_query", "")
        previous_questions: List[str] = safe_get(state, "previous_questions", [])
        messages = safe_get(state, "messages", [])
        combined_query = " ".join(q for q in [query] + previous_questions if q)
        
        user_name = decision.get("user_name")

        if user_name:
            content = (
                f"## Let’s keep the conversation respectful and focused on learning. \n"     
                f" How can I help you with the course content?\n    "
            )
        else:
            content = (
                f"## Let’s keep the conversation respectful and focused on learning. \n"
                f" How can I help you with the course content?\n"
            )

        response = self._build_response(
            content=content,
            chunks_used=[],
            video_suggestions=[],
            question_suggestions=[],
            short_topic="threadning",
            routing_reason=decision.get("reason", "threadning"),
        )

        return {
            "router_decision": decision,
            "node_response": self._response_to_dict(response),
        }
