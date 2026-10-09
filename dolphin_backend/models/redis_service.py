import json
from typing import Optional, List, Dict, Any
import redis.asyncio as redis
import inspect
from loguru import logger


class RedisService:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis: Optional[redis.Redis] = None

    # -----------------------------
    # CONNECT
    # -----------------------------
    async def connect(self):
        try:
            logger.info(f"Connecting to Redis at {self.redis_url}")

            self.redis = redis.from_url(
                self.redis_url,
                decode_responses=True
            )

            result = self.redis.ping()

            if inspect.isawaitable(result):
                await result

            logger.info("Redis connected successfully")

        except Exception as e:
            self.redis = None
            logger.warning(f"Redis connection failed: {e}")

    def is_connected(self) -> bool:
        return self.redis is not None

    # -----------------------------
    # ACTIVE SESSION
    # -----------------------------
    async def get_active_session(self, user_id: str) -> Optional[str]:
        if not self.redis:
            return None
        try:
            session = await self.redis.get(f"active_session:{user_id}")
            return session
        except Exception as e:
            logger.error(f"Redis error (get_active_session): {e}")
            return None

    async def set_active_session(self, user_id: str, session_id: str):
        if not self.redis:
            return
        try:
            await self.redis.set(f"active_session:{user_id}", session_id)
        except Exception as e:
            logger.error(f"Redis error (set_active_session): {e}")

    # -----------------------------
    # SESSION MESSAGES CACHE
    # -----------------------------
    async def get_session_messages(self, session_id: str) -> Optional[List[Dict]]:
        if not self.redis:
            return None
        try:
            data = await self.redis.get(f"session_cache:{session_id}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis error (get_session_messages): {e}")
            return None

    async def set_session_messages(
        self,
        session_id: str,
        messages: List[Dict],
        ttl: int = 3600
    ):
        if not self.redis:
            return
        try:
            await self.redis.set(
                f"session_cache:{session_id}",
                json.dumps(messages),
                ex=ttl
            )
        except Exception as e:
            logger.error(f"Redis error (set_session_messages): {e}")

    # -----------------------------
    # USER DATA CACHE
    # -----------------------------
    async def set_user_data(self, user_id: str, data: dict, ttl: int = 86400):
        if not self.redis:
            return
        try:
            await self.redis.set(
                f"user:{user_id}",
                json.dumps(data),
                ex=ttl
            )
            logger.info(f"Redis SET user:{user_id}")
        except Exception as e:
            logger.error(f"Redis error (set_user_data): {e}")

    async def get_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not self.redis:
            return None
        try:
            data = await self.redis.get(f"user:{user_id}")
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis error (get_user_data): {e}")
            return None

    async def delete_user_data(self, user_id: str):
        if not self.redis:
            return
        try:
            await self.redis.delete(f"user:{user_id}")
            logger.info(f"Redis DELETE user:{user_id}")
        except Exception as e:
            logger.error(f"Redis error (delete_user_data): {e}")

    # -----------------------------
    # ALIAS
    # -----------------------------
    async def get_user_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self.get_user_data(user_id)

    # -----------------------------
    # SESSION SUMMARY CACHE
    # -----------------------------
    async def set_session_summary(
        self,
        session_id: str,
        summary: str,
        ttl: int = 86400
    ):
        if not self.redis:
            return
        try:
            await self.redis.set(
                f"session_summary:{session_id}",
                summary,
                ex=ttl
            )
        except Exception as e:
            logger.error(f"Redis error (set_session_summary): {e}")

    async def get_session_summary(self, session_id: str) -> Optional[str]:
        if not self.redis:
            return None
        try:
            summary = await self.redis.get(f"session_summary:{session_id}")
            if summary:
                return summary
            return None
        except Exception as e:
            logger.error(f"Redis error (get_session_summary): {e}")
            return None

    async def delete_session_summary(self, session_id: str):
        if not self.redis:
            return
        try:
            await self.redis.delete(f"session_summary:{session_id}")
        except Exception as e:
            logger.error(f"Redis error (delete_session_summary): {e}")

    async def close(self):
        if not self.redis:
            return
        try:
            await self.redis.aclose()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Redis error (close): {e}")
        finally:
            self.redis = None        