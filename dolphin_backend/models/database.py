from __future__ import annotations

import asyncio
import asyncpg
from asyncpg import Pool
from typing import Optional
from loguru import logger
from config import settings

_pool: Optional[Pool] = None

# chat_sessions.messages canonical JSON structure:
# [
#   {
#     "role": "user" | "assistant",
#     "content": "...",  # string; markdown allowed for assistant replies
#     "timestamp": "2025-01-01T00:00:00.000000",
#     "category": "GREETING" | "QUERY" | "QUIZ" | "SUMMARY" | "FALLBACK",
#     "video_suggestions": [...],      # assistant only (QUERY/SUMMARY)
#     "question_suggestions": [...],   # assistant only (GREETING/QUERY/SUMMARY)
#   }
# ]


async def get_pool() -> Pool:
    """
    Get or create a global asyncpg pool.

    FIXES:
    - Recreate pool if it is closed or bound to a different/closed event loop.
    - Ensure safe reuse across lifespan restarts and request handlers.
    - Prevent connection leaks on remote database.
    """
    global _pool

    needs_new_pool = False
    if _pool is None or _pool.is_closing():
        needs_new_pool = True
    else:
        try:
            current_loop = asyncio.get_running_loop()
            pool_loop = getattr(_pool, "_loop", None)
            if pool_loop is None or pool_loop.is_closed() or pool_loop is not current_loop:
                needs_new_pool = True
        except Exception:
            needs_new_pool = True

    if needs_new_pool:
        if _pool is not None and not _pool.is_closing():
            try:
                _pool.terminate()
            except Exception:
                pass
        logger.info("📦 Creating PostgreSQL pool for current event loop")
        _pool = await asyncpg.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            min_size=1,
            max_size=4,
            command_timeout=60,
            timeout=30,
            max_inactive_connection_lifetime=60,
        )
        return _pool

    return _pool


async def close_pool() -> None:
    """
    Safely close the asyncpg pool.
    This is only called at FastAPI shutdown.
    """
    global _pool

    if _pool is not None and not _pool.is_closing():
        logger.info("🧹 Closing PostgreSQL pool")
        await _pool.close()

    _pool = None


async def init_feedback_tables(pool: Pool) -> None:
    """
    Ensure feedback_records, approved_feedback_memory, dpo_dataset, and dpo_training_jobs
    tables exist in PostgreSQL, and ensure performance indexes on chat_sessions exist.
    """
    import os
    try:
        schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sql", "feedback_schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                sql = f.read()
            async with pool.acquire() as conn:
                await conn.execute(sql)
            logger.info("✅ Feedback and DPO database tables initialized successfully")
    except Exception as e:
        logger.error(f"⚠️ Failed to auto-initialize feedback tables: {e}")

    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated 
                ON chat_sessions(user_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_is_saved 
                ON chat_sessions(user_id, is_saved, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated 
                ON chat_sessions(updated_at DESC);
            """)
            logger.info("✅ PostgreSQL performance indexes verified on chat_sessions")
    except Exception as e:
        logger.error(f"⚠️ Failed to create chat_sessions indexes: {e}")

