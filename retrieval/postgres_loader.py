from __future__ import annotations

from typing import Any, Dict, Iterable, List

from asyncpg import Pool


class PostgresLoader:
    def __init__(self, pool: Pool) -> None:
        self.pool = pool

    async def load_course_content(self) -> List[Dict[str, Any]]:
        """Load all rows from course_content for indexing."""

        # async with self.pool.acquire() as conn:
        #     records = await conn.fetch(
        #         """
        #         SELECT
        #             content_id,
        #             course_code,
        #             topic_code,
        #             topic_name,
        #             topic_video,
        #             topic_image,
        #             topic_pdf,
        #             topic_content,
        #             fetched_on
        #         FROM course_content
        #         ORDER BY content_id
        #         """
        #     )
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT
                    content_id,
                    course_code,
                    topic_code,
                    topic_name,
                    topic_video,
                    topic_pdf,
                    topic_content,
                    fetched_on
                FROM course_content
                ORDER BY content_id
                """
            )

        return [dict(record) for record in records]

    async def    fetch_course_content_by_ids(
        self, content_ids: Iterable[int] | Iterable[str]
    ) -> Dict[int, Dict[str, Any]]:
        """Fetch specific course_content rows keyed by content_id."""

        ids_list = [int(i) for i in content_ids if str(i).strip()]
        if not ids_list:
            return {}

        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT
                    content_id,
                    topic_name,
                    topic_code,
                    topic_content,
                    topic_video,
                    topic_image,
                    topic_pdf
                FROM course_content
                WHERE content_id = ANY($1)
                """,
                ids_list,
            )

        return {int(record["content_id"]): dict(record) for record in records}

