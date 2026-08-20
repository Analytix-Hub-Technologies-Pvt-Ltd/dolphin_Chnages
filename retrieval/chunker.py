from __future__ import annotations

from typing import Dict, List

from config import settings


class Chunker:
    def __init__(self, min_size: int | None = None, max_size: int | None = None) -> None:
        chunk_size = settings.chunk_size
        self.min_size = min_size or chunk_size
        self.max_size = max_size or chunk_size

    def chunk_content(self, rows: List[Dict]) -> List[Dict]:
        """Build semantic chunks directly from course_content rows.

        Each chunk always contains **Topic Name + Topic Content** combined so
        the embedding, FAISS metadata, and downstream retrieval all share the
        exact same text block. Media is not chunked or transformed here.
        """

        chunks: List[Dict] = []
        for row in rows:
            topic_name = row.get("topic_name", "").strip()
            topic_content = row.get("topic_content", "").strip()
            combined_content = f"Topic Name: {topic_name}\n\nTopic Content:\n{topic_content}"

            chunks.append(
                {
                    "content_id": row.get("content_id"),
                    "topic_name": topic_name,
                    "topic_content": topic_content,
                    "content": combined_content,
                    "topic_video": row.get("topic_video") or [],
                    "topic_image": row.get("topic_image") or [],
                    "topic_pdf": row.get("topic_pdf") or [],
                }
            )

        return chunks
