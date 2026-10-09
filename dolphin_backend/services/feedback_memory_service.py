from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple
import asyncpg
from loguru import logger

from services.embedding_service import EmbeddingService


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculate cosine similarity between two vector lists."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class FeedbackMemoryService:
    """
    Real-time semantic vector memory service for approved SME feedback corrections.
    Ensures multi-tenant isolation, real-time index updates, similarity thresholding,
    and automatic superseding of stale memories.
    """

    def __init__(self, pool: asyncpg.Pool, embedder: EmbeddingService) -> None:
        self.pool = pool
        self.embedder = embedder

    async def save_approved_memory(
        self,
        feedback_id: str,
        question: str,
        preferred_response: str,
        original_response: str,
        company_id: Optional[str] = None,
        ship_type: Optional[str] = None,
        approved_by: str = "admin",
    ) -> str:
        """
        Embeds the question and indexes it into approved_feedback_memory.
        Automatically supersedes/replaces older memories with exact matching queries
        or cosine similarity >= 0.92 within the same company/global scope.
        """
        clean_question = question.strip()
        clean_company = (company_id or "global").strip()
        clean_ship_type = ship_type.strip() if ship_type else None
        memory_id = f"mem_{feedback_id}"

        # 1. Generate embedding for the trigger question
        logger.info("🧠 Generating embedding for approved feedback memory: '{}'", clean_question[:100])
        embedding_vector = await self.embedder.embed_query(clean_question)

        async with self.pool.acquire() as conn:
            # 2. Check for duplicate or stale memories to supersede (>= 0.92 similarity or exact question)
            query_candidates = await conn.fetch(
                """
                SELECT memory_id, feedback_id, question, embedding
                FROM public.approved_feedback_memory
                WHERE (company_id = $1 OR company_id = 'global')
                  AND feedback_id != $2
                """,
                clean_company,
                feedback_id,
            )

            stale_memory_ids = []
            for row in query_candidates:
                row_q = (row["question"] or "").strip().lower()
                if row_q == clean_question.lower():
                    stale_memory_ids.append(row["memory_id"])
                    continue

                raw_emb = row["embedding"]
                if raw_emb:
                    try:
                        other_vec = json.loads(raw_emb) if isinstance(raw_emb, str) else raw_emb
                        if isinstance(other_vec, list) and cosine_similarity(embedding_vector, other_vec) >= 0.92:
                            stale_memory_ids.append(row["memory_id"])
                    except Exception as e:
                        logger.debug("Failed parsing embedding for memory {}: {}", row["memory_id"], e)

            if stale_memory_ids:
                logger.info("♻️ Superseding {} older matching memory records: {}", len(stale_memory_ids), stale_memory_ids)
                await conn.execute(
                    "DELETE FROM public.approved_feedback_memory WHERE memory_id = ANY($1::varchar[])",
                    stale_memory_ids,
                )

            # 3. Upsert current memory
            embedding_json = json.dumps(embedding_vector)
            await conn.execute(
                """
                INSERT INTO public.approved_feedback_memory (
                    memory_id, feedback_id, question, preferred_response, original_response,
                    company_id, ship_type, embedding, approved_by, approved_at, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, now(), now(), now())
                ON CONFLICT (memory_id) DO UPDATE SET
                    question = EXCLUDED.question,
                    preferred_response = EXCLUDED.preferred_response,
                    original_response = EXCLUDED.original_response,
                    company_id = EXCLUDED.company_id,
                    ship_type = EXCLUDED.ship_type,
                    embedding = EXCLUDED.embedding,
                    approved_by = EXCLUDED.approved_by,
                    approved_at = now(),
                    updated_at = now()
                """,
                memory_id,
                feedback_id,
                clean_question,
                preferred_response.strip(),
                original_response.strip(),
                clean_company,
                clean_ship_type,
                embedding_json,
                approved_by,
            )

            logger.success("✅ Successfully indexed approved feedback memory (id={})", memory_id)
            return memory_id

    async def remove_approved_memory(self, feedback_id: str) -> bool:
        """Purges memory when feedback is rejected or deleted."""
        async with self.pool.acquire() as conn:
            res = await conn.execute(
                "DELETE FROM public.approved_feedback_memory WHERE feedback_id = $1",
                feedback_id,
            )
            deleted = "DELETE 0" not in res
            if deleted:
                logger.info("🗑️ Removed memory for feedback_id={}", feedback_id)
            return deleted

    async def find_relevant_feedback_preference(
        self,
        query: str,
        user_profile: Optional[Dict[str, Any]] = None,
        min_similarity_threshold: float = 0.65,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the best matching approved feedback memory for an incoming chat query.
        - Multi-tenant isolation: Matches only company_id == user.company_id or company_id == 'global'.
        - Threshold filtering: >= 0.65.
        - Affinity boost: +0.05 bonus if memory's ship_type matches user's ship_type.
        """
        clean_query = (query or "").strip()
        if not clean_query:
            return None

        user_profile = user_profile or {}
        user_company = str(user_profile.get("company_id") or "global").strip()
        user_ship_type = str(user_profile.get("ship_type") or "").strip().lower()

        async with self.pool.acquire() as conn:
            # Query scoped strictly to user company or global
            rows = await conn.fetch(
                """
                SELECT memory_id, feedback_id, question, preferred_response, original_response,
                       company_id, ship_type, embedding, approved_by, approved_at
                FROM public.approved_feedback_memory
                WHERE company_id = $1 OR company_id = 'global'
                """,
                user_company,
            )

            if not rows:
                return None

            # Generate embedding for current query ONLY if records exist
            try:
                query_vector = await self.embedder.embed_query(clean_query)
            except Exception as e:
                logger.error("❌ Failed to embed query for feedback memory search: {}", e)
                return None

            best_match: Optional[Dict[str, Any]] = None
            highest_effective_sim = -1.0

            for row in rows:
                raw_emb = row["embedding"]
                if not raw_emb:
                    continue

                try:
                    mem_vec = json.loads(raw_emb) if isinstance(raw_emb, str) else raw_emb
                    if not isinstance(mem_vec, list):
                        continue

                    raw_sim = cosine_similarity(query_vector, mem_vec)
                    effective_sim = raw_sim

                    # Ship type affinity boost (+0.05 bonus similarity if matched)
                    mem_ship = (row["ship_type"] or "").strip().lower()
                    if mem_ship and user_ship_type and (mem_ship in user_ship_type or user_ship_type in mem_ship):
                        effective_sim += 0.05

                    if effective_sim >= min_similarity_threshold and effective_sim > highest_effective_sim:
                        highest_effective_sim = effective_sim
                        best_match = {
                            "memory_id": row["memory_id"],
                            "feedback_id": row["feedback_id"],
                            "question": row["question"],
                            "preferred_response": row["preferred_response"],
                            "original_response": row["original_response"],
                            "company_id": row["company_id"],
                            "ship_type": row["ship_type"],
                            "approved_by": row["approved_by"],
                            "approved_at": row["approved_at"].isoformat() if row["approved_at"] else None,
                            "raw_similarity": round(raw_sim, 4),
                            "effective_similarity": round(effective_sim, 4),
                        }
                except Exception as row_err:
                    logger.debug("Error computing similarity for row {}: {}", row["memory_id"], row_err)

            if best_match:
                logger.info(
                    "🎯 Found matching Feedback Memory! question='{}', raw_sim={:.3f}, effective_sim={:.3f}",
                    best_match["question"][:60],
                    best_match["raw_similarity"],
                    best_match["effective_similarity"],
                )
            return best_match
