from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from asyncpg import Pool
from loguru import logger

from models.node_response import NodeResponse


SESSION_EXPIRY_HOURS = 24


class SessionService:
    def __init__(self, pool: Pool) -> None:
        self.pool = pool
    
    async def _get_pool(self) -> Pool:
        """
        Get the pool, recreating it if it's been closed.
        This provides resilience against pool closure issues.
        """
        from models.database import get_pool
        
        # Check if current pool is closed
        if getattr(self.pool, "_closed", False):
            logger.warning("⚠️ SessionService pool is closed. Getting fresh pool...")
            self.pool = await get_pool()
        
        return self.pool

    async def _fetch_latest_session(self, user_id: str) -> Optional[Dict]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM chat_sessions WHERE user_id=$1 ORDER BY updated_at DESC LIMIT 1",
                user_id,
            )
        return dict(record) if record else None

    async def _create_session(self, user_id: str, title: Optional[str] = None) -> Dict:
        session_id = str(uuid.uuid4())
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            record = await conn.fetchrow(
                "INSERT INTO chat_sessions (session_id, user_id, title) VALUES ($1, $2, $3) RETURNING *",
                session_id,
                user_id,
                title,
            )
        return dict(record)
    
    async def get_user_by_id(self, user_id: str):
        query = "SELECT * FROM users WHERE id = $1"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, user_id)

    async def get_active_session(self, user_id: str) -> Dict:
        latest = await self._fetch_latest_session(user_id)
        if latest is None:
            return await self._create_session(user_id)
        updated_at = latest.get("updated_at")
        if updated_at and datetime.utcnow() - updated_at > timedelta(hours=SESSION_EXPIRY_HOURS):
            return await self._create_session(user_id)
        return latest

    async def create_session(self, user_id: str, title: Optional[str] = None) -> Dict:
        return await self._create_session(user_id, title)

    # async def get_session(self, session_id: str, user_id: str) -> Optional[Dict]:
    #     pool = await self._get_pool()
    #     async with pool.acquire() as conn:
    #         record = await conn.fetchrow(
    #             "SELECT * FROM chat_sessions WHERE session_id=$1 AND user_id=$2",
    #             session_id,
    #             user_id,
    #         )
    #     return dict(record) if record else None


    async def get_session(self, session_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            if user_id:
                record = await conn.fetchrow(
                    """
                    SELECT * FROM chat_sessions 
                    WHERE session_id=$1 AND user_id=$2
                    """,
                    session_id,
                    user_id,
                )

                # fallback if mismatch
                if not record:
                    record = await conn.fetchrow(
                        """
                        SELECT * FROM chat_sessions 
                        WHERE session_id=$1
                        """,
                        session_id,
                    )
            else:
                record = await conn.fetchrow(
                    """
                    SELECT * FROM chat_sessions 
                    WHERE session_id=$1
                    """,
                    session_id,
                )

        return dict(record) if record else None

    async def list_sessions(self, user_id: str, search: Optional[str] = None) -> List[Dict[str, Any]]:
        search_clause = ""
        params: List[Any] = [user_id]

        if search:
            search_clause = """
            AND (
                title ILIKE $2
                OR EXISTS (
                    SELECT 1 FROM jsonb_array_elements(messages) elem
                    WHERE (elem->>'content') ILIKE $2
                )
            )
            """
            params.append(f"%{search}%")

        query = f"""
            SELECT
                session_id,
                user_id,
                title,
                is_saved,
                created_at,
                updated_at,
                COALESCE(jsonb_array_length(messages), 0) AS message_count,
                messages -> -1 AS last_message
            FROM chat_sessions
            WHERE user_id=$1
            {search_clause}
            ORDER BY updated_at DESC
        """

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            records = await conn.fetch(query, *params)

        return [dict(record) for record in records]

    async def update_session_title(self, session_id: str, title: str) -> None:
        """Update the chat session title without altering other fields."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE chat_sessions SET title=$2 WHERE session_id=$1",
                session_id,
                title,
            )

    async def _ensure_session_title(self, session_id: str, fallback: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE chat_sessions
                SET title = CASE WHEN (title IS NULL OR title = '') THEN left($2, 60) ELSE title END
                WHERE session_id=$1
                """,
                session_id,
                fallback,
            )

    async def save_response(self, session_id: str, response: NodeResponse) -> None:
        """Backwards-compatible helper to persist an assistant reply."""
        response_text = getattr(response, "response", None) or getattr(response, "content", "")
        raw_videos = getattr(response, "video_suggestions", []) or []
        question_suggestions = list(getattr(response, "question_suggestions", []) or [])

        video_suggestions: List[Dict[str, str]] = []
        for video in raw_videos:
            data = video.model_dump() if hasattr(video, "model_dump") else video
            if not isinstance(data, dict):
                continue
            title = str(data.get("title") or "").strip()
            videourl = str(data.get("videourl") or data.get("url") or "").strip()
            if title or videourl:
                video_suggestions.append({"title": title, "videourl": videourl})

        session = await self.get_session(session_id, None)
        messages = session.get("messages", []) if session else []
        next_id = len(messages) + 1        

        payload = [
            {   
                "message_id": next_id,
                "role": "assistant",
                "content": response_text,
                "video_suggestions": video_suggestions,
                "question_suggestions": question_suggestions,
                "timestamp": datetime.utcnow().isoformat(),
                "command": getattr(response, "command", None),
            }
        ]

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE chat_sessions SET messages = COALESCE(messages, '[]'::jsonb) || $1::jsonb, updated_at=NOW() WHERE session_id=$2",
                json.dumps(payload, default=str),
                session_id,
            )

    async def save_user_message(self, session_id: str, message: str) -> Dict[str, Any]:
        session = await self.get_session(session_id, None)
        messages = session.get("messages", []) if session else []
        next_id = len(messages) + 1
        payload = {
            "message_id": next_id,
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat(),
            "command": None,
        }

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE chat_sessions SET messages = COALESCE(messages, '[]'::jsonb) || $1::jsonb, updated_at=NOW() WHERE session_id=$2",
                json.dumps([payload], default=str),
                session_id,
            )

        await self._ensure_session_title(session_id, message)
        return payload

    async def update_session_messages(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """Update the entire messages array for a session."""
        logger.info(f"💾 Updating session messages for {session_id}, count: {len(messages)}")

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE chat_sessions SET messages = $1::jsonb, updated_at = NOW() WHERE session_id = $2",
                json.dumps(messages, default=str),
                session_id,
            )
        logger.info(f"✅ Session messages updated for {session_id}")

    def convert_messages_for_llm(self, messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Convert stored messages into role/content format
        for LangGraph history input.
        Accepts both legacy (question/response) and new
        role/content schemas.
        """

        history: List[Dict[str, str]] = []

        for msg in messages or []:
            if not isinstance(msg, dict):
                continue

            if msg.get("role") in {"user", "assistant"} and msg.get("content"):
                history.append({"role": msg["role"], "content": str(msg.get("content"))})
                continue

            if "question" in msg:
                question = str(msg.get("question") or "")
                if question:
                    history.append({"role": "user", "content": question})
            elif "response" in msg:
                response_text = str(msg.get("response") or "")
                if response_text:
                    history.append({"role": "assistant", "content": response_text})

        return history

    async def save_session(self, session_id: str):
        query = """
            UPDATE chat_sessions
            SET
                is_saved = TRUE,
                updated_at = CURRENT_TIMESTAMP
            WHERE session_id = $1
            RETURNING *;
        """

        return await self.pool.fetchrow(query, session_id)
    
    async def toggle_save_session(self, session_id: str):
        query = """
            UPDATE chat_sessions
            SET
                is_saved = NOT COALESCE(is_saved, FALSE),
                updated_at = CURRENT_TIMESTAMP
            WHERE session_id = $1
            RETURNING *;
        """

        return await self.pool.fetchrow(query, session_id)
    
    async def get_saved_sessions(self, user_id: str):
        query = """
            SELECT
                session_id,
                user_id,
                title,
                is_saved,
                created_at,
                updated_at
            FROM chat_sessions
            WHERE user_id = $1
            AND is_saved = TRUE
            ORDER BY updated_at DESC;
        """

        rows = await self.pool.fetch(query, user_id)

        return [dict(row) for row in rows]
    

    async def delete_session(self, session_id: str):
        query = """
            DELETE FROM chat_sessions
            WHERE session_id = $1
            RETURNING session_id;
        """

        return await self.pool.fetchrow(query, session_id)

    async def get_all_sessions(self) -> list[dict]:
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT
                    u.id AS id,
                    u.name AS username,
                    cs.title AS chat_title,
                    cs.updated_at AS time,
                    cs.session_id AS session_id
                FROM public.chat_sessions cs
                LEFT JOIN public.users u
                    ON cs.user_id = u.id
                ORDER BY cs.updated_at DESC
                """
            )

        return [dict(record) for record in records]

    async def get_all_sessions_filter(
        self,
        session_date: Optional[date] = None,
        student_name: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        pool = await self._get_pool()

        where_clause = """
            FROM public.chat_sessions cs
            INNER JOIN public.users u
                ON cs.user_id = u.id
            WHERE 1=1
        """

        params = []
        param_index = 1

        if session_date:
            where_clause += f"""
                AND cs.created_at >= ${param_index}
                AND cs.created_at < ${param_index + 1}
            """

            params.append(session_date)
            params.append(session_date + timedelta(days=1))
            param_index += 2

        if student_name:
            where_clause += f"""
                AND u.name ILIKE ${param_index}
            """

            params.append(f"%{student_name}%")
            param_index += 1

        async with pool.acquire() as conn:

            # Total count
            total = await conn.fetchval(
                f"""
                SELECT COUNT(*)
                {where_clause}
                """,
                *params,
            )

            # Paginated data
            query = f"""
                SELECT
                    u.id AS id,
                    u.name AS username,
                    cs.title AS chat_title,
                    cs.updated_at AS time,
                    cs.session_id AS session_id
                {where_clause}
                ORDER BY cs.updated_at DESC
                LIMIT ${param_index}
                OFFSET ${param_index + 1}
            """

            records = await conn.fetch(
                query,
                *params,
                limit,
                offset,
            )

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "data": [dict(record) for record in records],
        }

    # async def get_all_sessions_filter(
    #     self,
    #     session_date: Optional[date] = None,
    #     student_name: Optional[str] = None,
    # ) -> list[dict]:
    #     pool = await self._get_pool()

    #     query = """
    #         SELECT
    #             u.id AS id,
    #             u.name AS username,
    #             cs.title AS chat_title,
    #             cs.updated_at AS time,
    #             cs.session_id AS session_id
    #         FROM public.chat_sessions cs
    #         INNER JOIN public.users u
    #             ON cs.user_id = u.id
    #         WHERE 1=1
    #     """

    #     params = []
    #     param_index = 1

    #     if session_date:
    #         query += f"""
    #             AND cs.created_at >= ${param_index}
    #             AND cs.created_at < ${param_index + 1}
    #         """

    #         params.append(session_date)
    #         params.append(session_date.fromordinal(session_date.toordinal() + 1))

    #         param_index += 2

    #     if student_name:
    #         query += f"""
    #             AND u.name ILIKE ${param_index}
    #         """

    #         params.append(f"%{student_name}%")
    #         param_index += 1

    #     query += """
    #         ORDER BY cs.updated_at DESC
    #     """

    #     async with pool.acquire() as conn:
    #         records = await conn.fetch(query, *params)

    #     return [dict(record) for record in records]