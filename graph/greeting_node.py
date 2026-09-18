from __future__ import annotations

from typing import Any, Dict, List
from graph.base_node import BaseNode
from services.suggestion_service import SuggestionService


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


class GreetingNode(BaseNode):
    def __init__(self, suggestion_service: SuggestionService) -> None:
        super().__init__("greeting")
        self.suggestion_service = suggestion_service

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        decision = safe_get(state, "router_decision", {})
        # ❌ DON'T use chunks from state - they contain videos!
        # chunks: List[Dict[str, Any]] = safe_get(state, "retrieval_chunks", [])

        query = safe_get(state, "current_query", "")
        previous_questions: List[str] = safe_get(state, "previous_questions", [])
        messages = safe_get(state, "messages", [])

        combined_query = " ".join(q for q in [query] + previous_questions if q)
        category = decision.get("category") or "GREETING"

        user_profile = safe_get(state, "user_profile", {}) or {}
        user_name = decision.get("user_name") or user_profile.get("user_name") or user_profile.get("name")
        greeting_body = (
            "Welcome to Dolphin AI. Answers to your questions will be based exclusively on our internal knowledge library. "
            "In addition, as your company has uploaded its SMS documents, responses will be tailored to align with your company's Safety Management System."
        )

        if user_name:
            content = f"Hello {user_name}!\n\n{greeting_body}"
        else:
            content = greeting_body

        # For greetings, skip suggestion generation (not needed, adds delay)
        # Greetings don't need follow-up questions
        dynamic_suggestions = []

        # ✅ CRITICAL FIX: Pass EMPTY chunks and explicit empty media
        response = self._build_response(
            content=content,
            chunks_used=[],  # ← Empty! Don't pass chunks that contain videos
            video_suggestions=[],  # ← Empty!
            question_suggestions=dynamic_suggestions,  # ← Empty for speed!
            short_topic=decision.get("short_topic", "greeting"),
            routing_reason=decision.get("reason", "greeting"),
            media={  # ← Explicitly empty media
                "videos": [],
                "images": [],
                "pdfs": []
            }
        )

        response_dict = self._response_to_dict(response)

        # ✅ SAFETY CHECK: Ensure no videos leaked through
        if response_dict.get("video_suggestions") or response_dict.get("videos"):
            from loguru import logger
            logger.error("[GREETING] BUG: Videos leaked into greeting! Removing them.")
            response_dict["video_suggestions"] = []
            response_dict["videos"] = []
            if "metadata" in response_dict:
                response_dict["metadata"]["video_suggestions"] = []
                response_dict["metadata"]["videos"] = []

        return {
            "router_decision": decision,
            "node_response": response_dict,
        }
