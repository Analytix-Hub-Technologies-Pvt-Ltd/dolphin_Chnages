# base_node_simple.py

from datetime import datetime, timezone
from typing import Any, Dict, List


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


class BaseNode:
    def __init__(self, node_type: str):
        self.node_type = node_type

    def build_response(
        self,
        content: str,
        chunks_used: List[Dict],
        video_suggestions: List[Dict],
        question_suggestions: List[str],
        short_topic: str,
        routing_reason: str,
        media: Dict[str, List[Dict]] | None = None,
    ) -> Dict[str, Any]:

        media = media or {"videos": [], "images": [], "pdfs": []}

        return {
            "type": self.node_type,
            "content": content,
            "chunks_used": chunks_used,
            "video_suggestions": video_suggestions,
            "videos": media.get("videos", []),
            "images": media.get("images", []),
            "pdfs": media.get("pdfs", []),
            "question_suggestions": question_suggestions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "short_topic": short_topic,
                "routing_reason": routing_reason,
            },
        }