# base_node.py
from __future__ import annotations

import abc
from datetime import datetime, timezone
from typing import Any, Dict, List

from loguru import logger

from models.node_response import NodeResponse


def safe_get(state: Any, key: str, default=None):
    """
    Allow both:
    - dict["key"]
    - GraphState.key
    WITHOUT changing any logic.
    """
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


class BaseNode(abc.ABC):
    """Abstract base class for LangGraph nodes."""

    node_type: str

    def __init__(self, node_type: str) -> None:
        self.node_type = node_type

    async def __call__(self, state: Any):
        """Allow instances to be used directly as langgraph callables."""
        return await self.run(state)

    def _build_response(
        self,
        content: str,
        chunks_used: List[Dict[str, Any]],
        video_suggestions: List[Dict[str, Any]],
        question_suggestions: List[str],
        short_topic: str,
        routing_reason: str,
        *,
        media: Dict[str, List[Dict[str, Any]]] | None = None,
    ) -> Dict[str, Any]:  # Changed return type to Dict
        logger.debug(
            "Building node response",
            node_type=self.node_type,
            short_topic=short_topic,
            routing_reason=routing_reason,
        )

        media_bundle = media or {"videos": [], "images": [], "pdfs": []}

        # Return as dictionary instead of NodeResponse object
        return {
            "type": self.node_type,
            "content": content,
            "chunks_used": chunks_used,
            "video_suggestions": video_suggestions,
            "videos": media_bundle.get("videos", []),
            "images": media_bundle.get("images", []),
            "pdfs": media_bundle.get("pdfs", []),
            "question_suggestions": question_suggestions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "short_topic": short_topic,
                "routing_reason": routing_reason,
                "videos": media_bundle.get("videos", []),
                "images": media_bundle.get("images", []),
                "pdfs": media_bundle.get("pdfs", []),
            },
        }

    def _response_to_dict(self, response: NodeResponse | Dict[str, Any]) -> Dict[str, Any]:
        """Normalize node responses to dictionaries.

        The graph now uses plain dicts for responses, but some callers may
        still construct ``NodeResponse`` objects. This helper tolerates both
        shapes and ensures consistent serialization of video suggestions and
        timestamps.
        """

        if isinstance(response, dict):
            raw_suggestions = response.get("video_suggestions") or []
            video_suggestions: List[Dict[str, Any]] = []
            for suggestion in raw_suggestions:
                if hasattr(suggestion, "model_dump"):
                    video_suggestions.append(suggestion.model_dump())
                elif isinstance(suggestion, dict):
                    video_suggestions.append(suggestion)
                else:
                    video_suggestions.append({"value": suggestion})

            timestamp = response.get("timestamp")
            if isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()

            return {
                **response,
                "video_suggestions": video_suggestions,
                "videos": list(response.get("videos") or []),
                "images": list(response.get("images") or []),
                "pdfs": list(response.get("pdfs") or []),
                "timestamp": timestamp,
            }

        video_suggestions: List[Dict[str, Any]] = []
        for suggestion in response.video_suggestions:
            if hasattr(suggestion, "model_dump"):
                video_suggestions.append(suggestion.model_dump())
            elif isinstance(suggestion, dict):
                video_suggestions.append(suggestion)
            else:
                video_suggestions.append({"value": suggestion})

        return {
            "type": response.type,
            "content": response.content,
            "chunks_used": response.chunks_used,
            "video_suggestions": video_suggestions,
            "videos": getattr(response, "videos", []) or [],
            "images": getattr(response, "images", []) or [],
            "pdfs": getattr(response, "pdfs", []) or [],
            "question_suggestions": response.question_suggestions,
            "timestamp": response.timestamp.isoformat() if response.timestamp else None,
            "metadata": response.metadata,
        }

    @abc.abstractmethod
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the node and update the graph state."""