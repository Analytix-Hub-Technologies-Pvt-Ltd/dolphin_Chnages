from __future__ import annotations

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
    - Recreate pool if it is closed.
    - Ensure safe reuse across lifespan restarts.
    """
    global _pool

    # Case 1 → No pool exists
    if _pool is None:
        logger.info("📦 Creating PostgreSQL pool (initial)")
        try:
            _pool = await asyncpg.create_pool(
                host=settings.db_host,
                port=settings.db_port,
                user=settings.db_user,
                password=settings.db_password,
                database=settings.db_name,
                min_size=2,
                max_size=20,  # ⚡ OPTIMIZATION: Increased from 10 to 20 for concurrent load
                command_timeout=60,
                timeout=30,
                max_inactive_connection_lifetime=300,
            )
        except Exception as e:
            logger.warning(
                "⚠️ PostgreSQL pool creation failed ({!r}). "
                "App will start without DB; pool will be retried on next access.",
                e,
            )
            return None
        return _pool

    # Case 2 → Pool exists but is closed
    if _pool.is_closing():
        logger.warning("⚠️ PostgreSQL pool is closed. Recreating...")
        _pool = await asyncpg.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            min_size=2,
            max_size=15,  # ⚡ OPTIMIZATION: Increased from 5 to 15 for concurrent load
            command_timeout=60,
            timeout=30,
            max_inactive_connection_lifetime=300,
        )

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
