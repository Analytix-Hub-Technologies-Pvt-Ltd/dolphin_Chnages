import json
from typing import Optional, List, Dict, Any
import redis.asyncio as redis
import inspect


class RedisService:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis: Optional[redis.Redis] = None

    # -----------------------------
    # 🔹 CONNECT
    # -----------------------------
    async def connect(self):
        try:
            print(f"[Redis] Connecting to {self.redis_url}")

            self.redis = redis.from_url(
                self.redis_url,
                decode_responses=True,
                protocol=2
            )

            result = self.redis.ping()

            if inspect.isawaitable(result):
                await result

            print("[Redis] connected successfully")

        except Exception as e:
            self.redis = None
            print(f"[Redis] connection failed: {e}")

    def is_connected(self) -> bool:
        return self.redis is not None

    # -----------------------------
    # 🔹 ACTIVE SESSION
    # -----------------------------
    async def get_active_session(self, user_id: str) -> Optional[str]:
        if not self.redis:
            print("[Redis] not connected (get_active_session)")
            return None
        try:
            session = await self.redis.get(f"active_session:{user_id}")
            print(f"[Redis] GET active_session: {session}")
            return session
        except Exception as e:
            print(f"[Redis] error (get_active_session): {e}")
            return None

    async def set_active_session(self, user_id: str, session_id: str):
        if not self.redis:
            print("[Redis] not connected (set_active_session)")
            return
        try:
            await self.redis.set(f"active_session:{user_id}", session_id)
            print(f"[Redis] SET active_session: {session_id}")
        except Exception as e:
            print(f"[Redis] error (set_active_session): {e}")

    # -----------------------------
    # 🔹 SESSION MESSAGES CACHE
    # -----------------------------
    async def get_session_messages(self, session_id: str) -> Optional[List[Dict]]:
        if not self.redis:
            print("[Redis] not connected (get_session_messages)")
            return None
        try:
            data = await self.redis.get(f"session_cache:{session_id}")
            if data:
                print("[Redis] HIT (messages)")
                return json.loads(data)
            else:
                print("[Redis] MISS (messages)")
                return None
        except Exception as e:
            print(f"[Redis] error (get_session_messages): {e}")
            return None

    async def set_session_messages(
        self,
        session_id: str,
        messages: List[Dict],
        ttl: int = 3600
    ):
        if not self.redis:
            print("[Redis] not connected (set_session_messages)")
            return
        try:
            await self.redis.set(
                f"session_cache:{session_id}",
                json.dumps(messages),
                ex=ttl
            )
            print(f"[Redis] SET messages (len={len(messages)})")
        except Exception as e:
            print(f"[Redis] error (set_session_messages): {e}")

    # -----------------------------
    # 🔹 USER DATA CACHE
    # -----------------------------
    async def set_user_data(self, user_id: str, data: dict, ttl: int = 86400):
        if not self.redis:
            print("[Redis] not connected (set_user_data)")
            return
        try:
            await self.redis.set(
                f"user:{user_id}",
                json.dumps(data),
                ex=ttl
            )
            print(f"[Redis] SET user:{user_id}")
            print(f"[Redis] Data: {data}")
        except Exception as e:
            print(f"[Redis] error (set_user_data): {e}")

    async def get_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not self.redis:
            print("[Redis] not connected (get_user_data)")
            return None
        try:
            data = await self.redis.get(f"user:{user_id}")
            if data:
                print(f"[Redis] HIT user: {user_id}")
                return json.loads(data)
            else:
                print(f"[Redis] MISS user: {user_id}")
                return None
        except Exception as e:
            print(f"[Redis] error (get_user_data): {e}")
            return None

    async def delete_user_data(self, user_id: str):
        if not self.redis:
            print("[Redis] not connected (delete_user_data)")
            return
        try:
            await self.redis.delete(f"user:{user_id}")
            print(f"[Redis] DELETE user: {user_id}")
        except Exception as e:
            print(f"[Redis] error (delete_user_data): {e}")

    # -----------------------------
    # 🔹 ALIAS (IMPORTANT 🔥)
    # -----------------------------
    # Your chat code uses get_user_details → map it here
    async def get_user_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self.get_user_data(user_id)


    # -----------------------------
    # 🔹 SESSION SUMMARY CACHE (NEW 🔥)
    # -----------------------------
    async def set_session_summary(
        self,
        session_id: str,
        summary: str,
        ttl: int = 86400
    ):
        if not self.redis:
            print("[Redis] not connected (set_session_summary)")
            return
        try:
            await self.redis.set(
                f"session_summary:{session_id}",
                summary,
                ex=ttl
            )
            print(f"[Redis] SET session_summary:{session_id}")
        except Exception as e:
            print(f"[Redis] error (set_session_summary): {e}")

    async def get_session_summary(self, session_id: str) -> Optional[str]:
        if not self.redis:
            print("[Redis] not connected (get_session_summary)")
            return None
        try:
            summary = await self.redis.get(f"session_summary:{session_id}")
            if summary:
                print(f"[Redis] HIT session_summary")
                return summary
            else:
                print(f"[Redis] MISS session_summary")
                return None
        except Exception as e:
            print(f"[Redis] error (get_session_summary): {e}")
            return None

    async def delete_session_summary(self, session_id: str):
        if not self.redis:
            print("[Redis] not connected (delete_session_summary)")
            return
        try:
            await self.redis.delete(f"session_summary:{session_id}")
            print(f"[Redis] DELETE session_summary:{session_id}")
        except Exception as e:
            print(f"[Redis] error (delete_session_summary): {e}")

    async def close(self):
        if not self.redis:
            print("[Redis] not connected (close)")
            return
        try:
            await self.redis.aclose()
            print("[Redis] connection closed")
        except Exception as e:
            print(f"[Redis] error (close): {e}")
        finally:
            self.redis = None

















# import json
# from typing import Optional, List, Dict, Any
# import redis.asyncio as redis
# import inspect


# class RedisService:
#     def __init__(self, redis_url: str = "redis://localhost:6379"):
#         self.redis_url = redis_url
#         self.redis: Optional[redis.Redis] = None

    
#     async def connect(self):
#         try:
#             print(f"🔍 Connecting to {self.redis_url}")

#             self.redis = redis.from_url(
#                 self.redis_url,
#                 decode_responses=True
#             )

#             result = self.redis.ping()

#             import inspect
#             if inspect.isawaitable(result):
#                 await result

#             print("✅ Redis connected successfully")

#         except Exception as e:
#             self.redis = None
#             print(f"❌ Redis connection failed: {e}")

#     def is_connected(self) -> bool:
#         return self.redis is not None

#     # -----------------------------
#     # 🔹 ACTIVE SESSION
#     # -----------------------------
#     async def get_active_session(self, user_id: str) -> Optional[str]:
#         if not self.redis:
#             print("⚠️ Redis not connected (get_active_session)")
#             return None
#         try:
#             session = await self.redis.get(f"active_session:{user_id}")
#             print(f"📥 Redis GET active_session: {session}")
#             return session
#         except Exception as e:
#             print(f"❌ Redis error (get_active_session): {e}")
#             return None

#     async def set_active_session(self, user_id: str, session_id: str):
#         if not self.redis:
#             print("⚠️ Redis not connected (set_active_session)")
#             return
#         try:
#             await self.redis.set(f"active_session:{user_id}", session_id)
#             print(f"📤 Redis SET active_session: {session_id}")
#         except Exception as e:
#             print(f"❌ Redis error (set_active_session): {e}")

#     # -----------------------------
#     # 🔹 SESSION CACHE
#     # -----------------------------
#     async def get_session_messages(self, session_id: str) -> Optional[List[Dict]]:
#         if not self.redis:
#             print("⚠️ Redis not connected (get_session_messages)")
#             return None
#         try:
#             data = await self.redis.get(f"session_cache:{session_id}")
#             if data:
#                 print("✅ Redis HIT (messages)")
#                 return json.loads(data)
#             else:
#                 print("⚠️ Redis MISS (messages)")
#                 return None
#         except Exception as e:
#             print(f"❌ Redis error (get_session_messages): {e}")
#             return None

#     async def set_session_messages(
#         self,
#         session_id: str,
#         messages: List[Dict],
#         ttl: int = 3600
#     ):
#         if not self.redis:
#             print("⚠️ Redis not connected (set_session_messages)")
#             return
#         try:
#             await self.redis.set(
#                 f"session_cache:{session_id}",
#                 json.dumps(messages),
#                 ex=ttl
#             )
#             print(f"📤 Redis SET messages (len={len(messages)})")
#         except Exception as e:
#             print(f"❌ Redis error (set_session_messages): {e}")


#         # -----------------------------
#     # 🔹 USER DATA CACHE
#     # -----------------------------
#     async def set_user_data(self, user_id: str, data: dict, ttl: int = 86400):
#         if not self.redis:
#             print("⚠️ Redis not connected (set_user_data)")
#             return
#         try:
#             await self.redis.set(
#                 f"user:{user_id}",
#                 json.dumps(data),
#                 ex=ttl
#             )
#             print(f"📤 Redis SET user:{user_id}")
#             print(f"📦 Data: {data}")   # 👈 ADD THIS
#         except Exception as e:
#             print(f"❌ Redis error (set_user_data): {e}")

#     async def get_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
#         if not self.redis:
#             print("⚠️ Redis not connected (get_user_data)")
#             return None
#         try:
#             data = await self.redis.get(f"user:{user_id}")
#             if data:
#                 print(f"✅ Redis HIT user: {user_id}")
#                 return json.loads(data)
#             else:
#                 print(f"⚠️ Redis MISS user: {user_id}")
#                 return None
#         except Exception as e:
#             print(f"❌ Redis error (get_user_data): {e}")
#             return None

#     async def delete_user_data(self, user_id: str):
#         if not self.redis:
#             print("⚠️ Redis not connected (delete_user_data)")
#             return
#         try:
#             await self.redis.delete(f"user:{user_id}")
#             print(f"🗑️ Redis DELETE user: {user_id}")
#         except Exception as e:
#             print(f"❌ Redis error (delete_user_data): {e}")        