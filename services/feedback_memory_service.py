from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional
from asyncpg import Pool
from loguru import logger

from services.embedding_service import EmbeddingService


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two vector lists."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for a, b in zip(vec1, vec2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b
    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm1) * math.sqrt(norm2))


class FeedbackMemoryService:
    def __init__(self, pool: Pool, embedding_service: EmbeddingService) -> None:
        self.pool = pool
        self.embedding_service = embedding_service

    async def save_approved_memory(
        self,
        feedback_id: str,
        question: str,
        preferred_response: str,
        original_response: str,
        company_id: Optional[str],
        ship_type: Optional[str],
        approved_by: str = "admin",
    ) -> Dict[str, Any]:
        """
        Generate embedding for approved question and save/upsert to approved_feedback_memory.
        Supersedes and replaces any previous memory with matching feedback_id or matching question in the company.
        """
        clean_q = (question or "").strip()
        emb = await self.embedding_service.embed_query(clean_q)
        emb_json = json.dumps(emb)

        comp_id = str(company_id).strip() if company_id else "global"
        st = str(ship_type).strip() if ship_type else None
        mem_id = f"mem_{feedback_id}"

        query = """
        INSERT INTO public.approved_feedback_memory (
            memory_id, feedback_id, question, preferred_response, original_response,
            company_id, ship_type, embedding, approved_by, approved_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, now(), now())
        ON CONFLICT (memory_id) DO UPDATE SET
            feedback_id = EXCLUDED.feedback_id,
            question = EXCLUDED.question,
            preferred_response = EXCLUDED.preferred_response,
            original_response = EXCLUDED.original_response,
            company_id = EXCLUDED.company_id,
            ship_type = EXCLUDED.ship_type,
            embedding = EXCLUDED.embedding,
            approved_by = EXCLUDED.approved_by,
            approved_at = now(),
            updated_at = now()
        RETURNING memory_id, feedback_id, question, company_id, ship_type, approved_at;
        """

        async with self.pool.acquire() as conn:
            # 1. Clean up existing memory for this feedback_id
            await conn.execute("DELETE FROM public.approved_feedback_memory WHERE feedback_id = $1", feedback_id)

            # 2. Supersede any older memories with exact matching question for this company or aliases
            comp_filter = [comp_id]
            if comp_id in {"8", "CMS Demo Company"}:
                comp_filter.extend(["8", "CMS Demo Company"])

            await conn.execute(
                """
                DELETE FROM public.approved_feedback_memory
                WHERE LOWER(TRIM(question)) = LOWER(TRIM($1))
                  AND (company_id = ANY($2::text[]) OR company_id = 'global' OR company_id IS NULL OR company_id = '');
                """,
                clean_q,
                comp_filter,
            )

            # 3. Check for high-similarity existing memories in same company (>= 0.92 similarity) to prevent stale duplicates
            existing_rows = await conn.fetch(
                """
                SELECT memory_id, embedding
                FROM public.approved_feedback_memory
                WHERE (company_id = ANY($1::text[]) OR company_id = 'global' OR company_id IS NULL OR company_id = '');
                """,
                comp_filter,
            )
            for er in existing_rows:
                raw_e = er["embedding"]
                if isinstance(raw_e, str):
                    try:
                        mem_e = json.loads(raw_e)
                    except Exception:
                        continue
                elif isinstance(raw_e, list):
                    mem_e = raw_e
                else:
                    continue

                if cosine_similarity(emb, mem_e) >= 0.92:
                    await conn.execute(
                        "DELETE FROM public.approved_feedback_memory WHERE memory_id = $1",
                        er["memory_id"],
                    )
                    logger.info(f"🔄 [FeedbackMemory] Superseded duplicate memory '{er['memory_id']}' for company '{comp_id}'")

            # 4. Insert the new approved memory
            row = await conn.fetchrow(
                query,
                mem_id,
                feedback_id,
                clean_q,
                preferred_response,
                original_response,
                comp_id,
                st,
                emb_json,
                approved_by,
            )
            logger.info(f"🧠 [FeedbackMemory] Indexed approved memory for feedback '{feedback_id}' (Company: '{comp_id}')")
            return dict(row) if row else {}

    async def remove_approved_memory(self, feedback_id: str) -> None:
        """Remove memory record if feedback is rejected or unapproved."""
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM public.approved_feedback_memory WHERE feedback_id = $1", feedback_id)
            logger.info(f"🗑️ [FeedbackMemory] Deleted approved memory for feedback '{feedback_id}'")

    async def find_relevant_feedback_preference(
        self,
        query: str,
        company_id: Optional[str] = None,
        ship_type: Optional[str] = None,
        threshold: float = 0.65,
        query_embedding: Optional[List[float]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Search for semantically similar approved feedback memory for any query and company dynamically.
        Strict company isolation: Company A feedback NEVER influences Company B.
        Allows global feedback for general maritime standards and prioritizes exact company match.
        """
        if not query and not query_embedding:
            return None

        comp_id = str(company_id).strip() if company_id else None

        if comp_id and comp_id.lower() != "global":
            # Dynamic multi-tenant retrieval: fetch approved memories for this specific company OR global items
            comp_list = [comp_id]
            if comp_id in {"8", "CMS Demo Company"}:
                comp_list = ["8", "CMS Demo Company"]

            fetch_sql = """
            SELECT memory_id, feedback_id, question, preferred_response, original_response, company_id, ship_type, embedding, approved_at
            FROM public.approved_feedback_memory
            WHERE company_id = ANY($1::text[]) OR company_id = 'global' OR company_id IS NULL OR company_id = ''
            ORDER BY approved_at DESC
            LIMIT 150;
            """
            params = [comp_list]
        else:
            # General query without specific company: fetch only global/generic approved memories
            fetch_sql = """
            SELECT memory_id, feedback_id, question, preferred_response, original_response, company_id, ship_type, embedding, approved_at
            FROM public.approved_feedback_memory
            WHERE company_id = 'global' OR company_id IS NULL OR company_id = ''
            ORDER BY approved_at DESC
            LIMIT 150;
            """
            params = []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(fetch_sql, *params) if params else await conn.fetch(fetch_sql)

        if not rows:
            return None

        if query_embedding is None:
            query_embedding = await self.embedding_service.embed_query(query)

        best_match: Optional[Dict[str, Any]] = None
        best_score = -1.0
        target_ship = str(ship_type).strip().lower() if ship_type else None

        for r in rows:
            raw_emb = r["embedding"]
            if isinstance(raw_emb, str):
                try:
                    mem_emb = json.loads(raw_emb)
                except Exception:
                    continue
            elif isinstance(raw_emb, list):
                mem_emb = raw_emb
            else:
                continue

            sim = cosine_similarity(query_embedding, mem_emb)
            effective_sim = sim

            # Dynamic Company Match Priority: Boost exact company match (+0.05) over global
            r_comp = str(r["company_id"]).strip() if r["company_id"] else ""
            if comp_id and r_comp and (comp_id.lower() == r_comp.lower() or (comp_id in {"8", "CMS Demo Company"} and r_comp in {"8", "CMS Demo Company"})):
                effective_sim += 0.05

            # Dynamic Ship Type Priority: Boost matching ship type (+0.03)
            mem_ship = str(r["ship_type"]).strip().lower() if r["ship_type"] else None
            if target_ship and mem_ship and target_ship == mem_ship:
                effective_sim += 0.03

            if effective_sim >= threshold and effective_sim > best_score:
                best_score = effective_sim
                best_match = {
                    "memory_id": r["memory_id"],
                    "feedback_id": r["feedback_id"],
                    "question": r["question"],
                    "preferred_response": r["preferred_response"],
                    "original_response": r["original_response"],
                    "company_id": r["company_id"],
                    "ship_type": r["ship_type"],
                    "similarity": round(sim, 4),
                    "effective_similarity": round(effective_sim, 4),
                }

        if best_match:
            logger.success(
                f"🎯 [FeedbackMemory Hit] Matched approved feedback '{best_match['feedback_id']}' "
                f"(Company: '{best_match.get('company_id')}') with similarity {best_match['similarity']} "
                f"(Effective: {best_match['effective_similarity']}) for query '{query[:60]}...'"
            )

        return best_match
