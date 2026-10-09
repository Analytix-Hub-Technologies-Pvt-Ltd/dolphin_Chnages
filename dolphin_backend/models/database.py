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
    - Low min_size (1) and moderate max_size (5) to prevent exhausting shared remote DB connections.
    - Shorter max_inactive_connection_lifetime (30s) to release idle connections immediately.
    - Automatic retry logic with backoff for TooManyConnectionsError.
    - Recreate pool if it is closed.
    - Ensure safe reuse across lifespan restarts.
    """
    global _pool

    async def _create_resilient_pool(min_s: int = 1, max_s: int = 5) -> Pool:
        import asyncio
        last_err = None
        for attempt in range(1, 4):
            try:
                return await asyncpg.create_pool(
                    host=settings.db_host,
                    port=settings.db_port,
                    user=settings.db_user,
                    password=settings.db_password,
                    database=settings.db_name,
                    min_size=min_s,
                    max_size=max_s,
                    command_timeout=60,
                    timeout=15,
                    max_inactive_connection_lifetime=30,
                )
            except (asyncpg.TooManyConnectionsError, OSError) as e:
                last_err = e
                logger.warning(f"⚠️ DB connection attempt {attempt}/3 failed ({e}). Retrying with smaller pool in 1.5s...")
                await asyncio.sleep(1.5)
                min_s = 1
                max_s = max(2, max_s - 2)
        raise last_err

    # Case 1 → No pool exists
    if _pool is None:
        logger.info("📦 Creating PostgreSQL pool (initial)")
        _pool = await _create_resilient_pool(min_s=1, max_s=5)
        return _pool

    # Case 2 → Pool exists but is closed
    if _pool.is_closing():
        logger.warning("⚠️ PostgreSQL pool is closed. Recreating...")
        _pool = await _create_resilient_pool(min_s=1, max_s=5)

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
