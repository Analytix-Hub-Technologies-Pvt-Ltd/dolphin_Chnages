from __future__ import annotations

from typing import Any, Dict, List
from graph.base_node import BaseNode
from services.suggestion_service import SuggestionService


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


class WellWishNode(BaseNode):
    def __init__(self, suggestion_service: SuggestionService) -> None:
        super().__init__("well_wish")
        self.suggestion_service = suggestion_service

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:

        decision = safe_get(state, "router_decision", {})
        # ❌ DON'T use chunks from state - they contain videos!
        # chunks: List[Dict[str, Any]] = safe_get(state, "retrieval_chunks", [])
        query = safe_get(state, "current_query", "")
        previous_questions: List[str] = safe_get(state, "previous_questions", [])
        messages = safe_get(state, "messages", [])
        combined_query = " ".join(q for q in [query] + previous_questions if q)
        
        user_name = decision.get("user_name")

        if user_name:
            content = (
                f"## I'm doing well, thank you!\n"
                f" How can I assist you with the marine course today?\n"    
            )
        else:
            content = (
                f"## I'm doing well, thank you!\n"
                f" How can I assist you with the marine course today?\n"
            )

        # For well-wishes, skip suggestion generation (not needed, adds delay)
        dynamic_suggestions = []

        # ✅ CRITICAL: Pass EMPTY chunks and explicit empty media to prevent video leakage
        response = self._build_response(
            content=content,
            chunks_used=[],  # ← Empty! Don't pass chunks
            video_suggestions=[],  # ← Empty!
            question_suggestions=dynamic_suggestions,  # ← Empty for speed!
            short_topic="well_wish",
            routing_reason=decision.get("reason", "well_wish"),
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
            logger.error("[WELL_WISH] BUG: Videos leaked! Removing them.")
            response_dict["video_suggestions"] = []
            response_dict["videos"] = []
            if "metadata" in response_dict:
                response_dict["metadata"]["video_suggestions"] = []
                response_dict["metadata"]["videos"] = []

        return {
            "router_decision": decision,
            "node_response": response_dict,
        }
