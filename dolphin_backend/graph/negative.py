from __future__ import annotations

from typing import Any, Dict, List
from graph.base_node import BaseNode
from services.suggestion_service import SuggestionService


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


class NegativeNode(BaseNode):
    def __init__(self, suggestion_service: SuggestionService) -> None:
        super().__init__("negative")
        self.suggestion_service = suggestion_service

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:

        # decision = safe_get(state, "router_decision", {})
        decision: Dict[str, Any] = safe_get(state, "router_decision", {}) or {}
        # chunks: List[Dict[str, Any]] = safe_get(state, "retrieval_chunks", [])
        chunks: List[Dict[str, Any]] = safe_get(state, "retrieval_chunks", []) or []
        query = safe_get(state, "current_query", "")
        # previous_questions: List[str] = safe_get(state, "previous_questions", [])
        previous_questions: List[str] = safe_get(state, "previous_questions", []) or []
        messages = safe_get(state, "messages", [])
        combined_query = " ".join(q for q in [query] + previous_questions if q)
        
        user_name = decision.get("user_name")
        
        # If chunks are available, this might be a misclassified query - provide helpful response
        if chunks and len(chunks) > 0:
            # Check if query contains workplace safety keywords (might have been misclassified)
            query_lower = query.lower()
            workplace_safety_keywords = [
                "harassment", "harassing", "harassed", "bullying", "bullied", 
                "intoxicated", "intoxication", "crew member", "crew management",
                "workplace", "incident", "advice", "how should", "what should",
                "how to handle", "what do i do"
            ]
            
            if any(kw in query_lower for kw in workplace_safety_keywords):
                # This is likely a legitimate workplace safety question that was misclassified
                # Provide a helpful response instead of the negative feedback message
                content = (
                    "I understand you're asking about a workplace situation. "
                    "Let me help you find relevant information about crew management and safety procedures. "
                    "Please rephrase your question as a specific query about the topic, and I'll provide detailed guidance.\n\n"
                    "For example:\n"
                    "- 'What are the procedures for handling crew member misconduct?'\n"
                    "- 'How should workplace harassment be reported?'\n"
                    "- 'What are the safety protocols for dealing with intoxicated crew members?'"
                )
            else:
                # Standard negative feedback response
                if user_name:
                    content = (
                        f"## I'm sorry this didn't feel helpful to you.\n"     
                        f"Please let me know what part you'd like explained differently, and I'll do my best to assist.\n"
                    )
                else:
                    content = (
                        "## I'm sorry this didn't feel helpful to you.\n"
                        "Please let me know what part you'd like explained differently, and I'll do my best to assist.\n"
                    )
        else:
            # No chunks available - standard negative feedback response
            if user_name:
                content = (
                    f"## I'm sorry this didn't feel helpful to you.\n"     
                    f"Please let me know what part you'd like explained differently, and I'll do my best to assist.\n"
                )
            else:
                content = (
                    "## I'm sorry this didn't feel helpful to you.\n"
                    "Please let me know what part you'd like explained differently, and I'll do my best to assist.\n"
                )

        response = self._build_response(
            content=content,
            chunks_used=[],
            video_suggestions=[],
            question_suggestions=[],
            short_topic="negative",
            routing_reason=decision.get("reason", "negative"),
        )

        return {
            "router_decision": decision,
            "node_response": self._response_to_dict(response),
        }
