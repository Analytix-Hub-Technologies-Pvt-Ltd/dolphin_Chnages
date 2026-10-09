import asyncio
import json
import math
import os
import pickle
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from asyncpg import Pool
from loguru import logger

CACHE_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "approved_memory_cache.pkl")


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two vector floats."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class ApprovedMemoryService:
    def __init__(self, pool: Pool, embedder=None) -> None:
        self.pool = pool
        self.embedder = embedder
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 600.0  # 10 minutes cache TTL
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _load_cache_from_disk(self) -> Optional[List[Dict[str, Any]]]:
        if os.path.exists(CACHE_FILE_PATH):
            try:
                with open(CACHE_FILE_PATH, "rb") as f:
                    items = pickle.load(f)
                if isinstance(items, list):
                    logger.info(f"⚡ Loaded {len(items)} approved memory items from local disk cache")
                    return items
            except Exception as e:
                logger.warning(f"Failed to load approved memory disk cache: {e}")
        return None

    def _save_cache_to_disk(self, items: List[Dict[str, Any]]) -> None:
        try:
            os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)
            with open(CACHE_FILE_PATH, "wb") as f:
                pickle.dump(items, f)
        except Exception as e:
            logger.warning(f"Failed to save approved memory disk cache: {e}")

    def invalidate_cache(self) -> None:
        """Invalidate the in-memory cache so next search refreshes from DB."""
        self._cache = None
        self._cache_timestamp = 0.0
        if os.path.exists(CACHE_FILE_PATH):
            try:
                os.remove(CACHE_FILE_PATH)
            except OSError:
                pass
        logger.info("🧹 In-memory approved feedback memory cache invalidated")

    async def warmup_cache(self) -> None:
        """Pre-warm in-memory cache at server startup."""
        await self._ensure_cache()

    async def refresh_cache(self) -> List[Dict[str, Any]]:
        """Fetch active items from PostgreSQL, parse vectors once, and persist to RAM and disk."""
        await self.init_table()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT memory_id, feedback_id, question, preferred_response, original_response, company_id, ship_type, embedding, updated_at
                FROM public.approved_feedback_memory
                WHERE is_active = TRUE
                ORDER BY updated_at DESC;
                """
            )
        cached: List[Dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            q_text = (item.get("question") or "").strip()
            item["_clean_q"] = q_text.lower()
            norm_q = re.sub(r"[^\w\s]", "", q_text.lower()).strip()
            item["_norm_q"] = " ".join(norm_q.split())
            emb_raw = item.get("embedding")
            parsed_vec = None
            if emb_raw:
                try:
                    parsed_vec = json.loads(emb_raw) if isinstance(emb_raw, str) else emb_raw
                except Exception:
                    pass
            item["_parsed_vec"] = parsed_vec
            item.pop("embedding", None)
            cached.append(item)

        self._cache = cached
        self._cache_timestamp = time.perf_counter()
        self._save_cache_to_disk(cached)
        logger.info(f"⚡ Refreshed approved memory cache ({len(cached)} items in RAM & disk)")
        return self._cache

    async def _ensure_cache(self) -> List[Dict[str, Any]]:
        now = time.perf_counter()
        if self._cache is not None and (now - self._cache_timestamp) < self._cache_ttl:
            return self._cache

        lock = self._get_lock()
        async with lock:
            if self._cache is not None and (time.perf_counter() - self._cache_timestamp) < self._cache_ttl:
                return self._cache

            # Try disk cache first (instant sub-millisecond load)
            disk_items = self._load_cache_from_disk()
            if disk_items is not None:
                self._cache = disk_items
                self._cache_timestamp = time.perf_counter()
                return self._cache

            # Fallback to DB fetch
            return await self.refresh_cache()

    async def init_table(self) -> None:
        """Ensure approved_feedback_memory table exists and has proper schema."""
        query = """
        CREATE TABLE IF NOT EXISTS public.approved_feedback_memory (
            memory_id TEXT PRIMARY KEY,
            feedback_id TEXT UNIQUE NOT NULL,
            question TEXT NOT NULL,
            preferred_response TEXT NOT NULL,
            original_response TEXT,
            company_id TEXT,
            ship_type TEXT,
            embedding JSONB,
            approved_by TEXT,
            approved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_afm_active ON public.approved_feedback_memory (is_active);
        CREATE INDEX IF NOT EXISTS idx_afm_company ON public.approved_feedback_memory (company_id);
        CREATE INDEX IF NOT EXISTS idx_afm_feedback_id ON public.approved_feedback_memory (feedback_id);
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query)

    async def sync_feedback_approval(
        self,
        feedback_id: Any,
        question: str,
        preferred_response: str,
        original_response: Optional[str] = None,
        company_id: Optional[str] = None,
        ship_type: Optional[str] = None,
        approved_by: Optional[str] = None,
        is_active: bool = True,
    ) -> None:
        """Immediately store or update an approved feedback item into active memory."""
        await self.init_table()
        fb_id_str = str(feedback_id)
        memory_id = f"mem_fb_{fb_id_str}"

        if not is_active:
            # Deactivate memory item
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE public.approved_feedback_memory
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE feedback_id = $1;
                    """,
                    fb_id_str,
                )
            logger.info(f"Deactivated approved feedback memory for feedback_id={fb_id_str}")
            try:
                await self.refresh_cache()
            except Exception as e:
                logger.warning(f"Failed to refresh approved memory cache after deactivation: {e}")
            return

        # Generate embedding for question if embedder is available
        embedding_json = None
        if self.embedder:
            try:
                vec = await self.embedder.embed_query(question)
                if vec:
                    embedding_json = json.dumps(vec)
            except Exception as e:
                logger.warning(f"Failed to generate embedding for approved feedback memory: {e}")

        query = """
        INSERT INTO public.approved_feedback_memory (
            memory_id, feedback_id, question, preferred_response,
            original_response, company_id, ship_type, embedding,
            approved_by, approved_at, is_active, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, CURRENT_TIMESTAMP, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        ON CONFLICT (feedback_id) DO UPDATE SET
            question = EXCLUDED.question,
            preferred_response = EXCLUDED.preferred_response,
            original_response = EXCLUDED.original_response,
            company_id = EXCLUDED.company_id,
            ship_type = EXCLUDED.ship_type,
            embedding = COALESCE(EXCLUDED.embedding, approved_feedback_memory.embedding),
            approved_by = EXCLUDED.approved_by,
            approved_at = CURRENT_TIMESTAMP,
            is_active = TRUE,
            updated_at = CURRENT_TIMESTAMP;
        """

        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                memory_id,
                fb_id_str,
                question,
                preferred_response,
                original_response or preferred_response,
                str(company_id) if (company_id is not None and str(company_id).strip() != "") else "global",
                ship_type or "All",
                embedding_json,
                approved_by or "SME Reviewer",
            )

        logger.info(f"✅ Synced approved feedback into immediate memory: id={fb_id_str}, q='{question[:60]}'")
        try:
            await self.refresh_cache()
        except Exception as e:
            logger.warning(f"Failed to refresh approved memory cache after sync: {e}")

    async def search_approved_memory(
        self,
        query_text: str,
        company_id: Optional[str] = None,
        similarity_threshold: float = 0.70,
        query_vector: Optional[List[float]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Search approved memory for matching questions using cached in-memory exact and vector similarity."""
        if not query_text or not query_text.strip():
            return None

        cleaned_q = query_text.strip()
        cleaned_lower = cleaned_q.lower()
        normalized_q = re.sub(r"[^\w\s]", "", cleaned_lower).strip()
        normalized_q = " ".join(normalized_q.split())

        target_cid = str(company_id).strip().lower() if (company_id is not None and str(company_id).strip() != "") else None

        def _matches_company(item_cid: Optional[str]) -> bool:
            if target_cid is None or target_cid in ("", "global", "all"):
                return True
            if item_cid is None:
                return True
            s = str(item_cid).strip().lower()
            return s in ("", "global", "all", target_cid)

        # ⚡ Load from in-memory / disk cache (instant ~0.01ms)
        cached_items = await self._ensure_cache()
        if not cached_items:
            return None

        # 1. Fast In-Memory Exact or Punctuation-Normalized Match (~0.01ms)
        for item in cached_items:
            if not _matches_company(item.get("company_id")):
                continue
            if item.get("_clean_q") == cleaned_lower or item.get("_norm_q") == normalized_q:
                logger.info(f"🎯 Exact text match found in approved feedback memory: id={item['feedback_id']}")
                return {
                    "memory_id": item["memory_id"],
                    "feedback_id": item["feedback_id"],
                    "question": item["question"],
                    "preferred_response": item["preferred_response"],
                    "original_response": item.get("original_response") or item["preferred_response"],
                    "company_id": item["company_id"],
                    "ship_type": item["ship_type"],
                    "match_type": "exact",
                    "score": 1.0,
                }

        # 2. Semantic Vector Similarity Search in RAM (~0.5ms)
        candidate_items = [
            item for item in cached_items
            if item.get("_parsed_vec") and _matches_company(item.get("company_id"))
        ]
        if not candidate_items:
            return None

        # Reuse provided vector or embed only if needed
        query_vec = query_vector
        if query_vec is None:
            if not self.embedder:
                return None
            try:
                query_vec = await self.embedder.embed_query(cleaned_q)
            except Exception as e:
                logger.warning(f"Could not embed query for memory search: {e}")
                return None

        best_match = None
        best_score = 0.0

        for item in candidate_items:
            vec = item["_parsed_vec"]
            score = cosine_similarity(query_vec, vec)
            if score > best_score:
                best_score = score
                best_match = item

        if best_match and best_score >= similarity_threshold:
            logger.info(
                f"🎯 Semantic match in approved feedback memory: id={best_match['feedback_id']}, score={best_score:.3f}"
            )
            return {
                "memory_id": best_match["memory_id"],
                "feedback_id": best_match["feedback_id"],
                "question": best_match["question"],
                "preferred_response": best_match["preferred_response"],
                "original_response": best_match.get("original_response") or best_match["preferred_response"],
                "company_id": best_match["company_id"],
                "ship_type": best_match["ship_type"],
                "match_type": "semantic",
                "score": best_score,
            }

        return None
