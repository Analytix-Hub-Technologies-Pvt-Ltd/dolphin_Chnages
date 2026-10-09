from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional
import asyncpg
from loguru import logger


class DPOService:
    """
    Service for managing Direct Preference Optimization (DPO) datasets
    and triggering/tracking background LLM fine-tuning jobs.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def add_dpo_pair(
        self,
        feedback_id: str,
        prompt: str,
        chosen: str,
        rejected: str,
        company_id: Optional[str] = None,
        ship_type: Optional[str] = None,
        dataset_version: str = "v1.0",
    ) -> int:
        """
        Inserts or updates a prompt-chosen-rejected pair for DPO alignment training.
        """
        async with self.pool.acquire() as conn:
            # Check if this feedback_id already has a DPO entry
            existing = await conn.fetchval(
                "SELECT dpo_id FROM public.dpo_dataset WHERE feedback_id = $1",
                feedback_id,
            )

            if existing:
                await conn.execute(
                    """
                    UPDATE public.dpo_dataset
                    SET prompt = $1, chosen = $2, rejected = $3, company_id = $4,
                        ship_type = $5, dataset_version = $6, updated_at = now()
                    WHERE feedback_id = $7
                    """,
                    prompt.strip(),
                    chosen.strip(),
                    rejected.strip(),
                    company_id,
                    ship_type,
                    dataset_version,
                    feedback_id,
                )
                logger.info("Updated DPO dataset pair for feedback_id={}", feedback_id)
                return existing

            dpo_id = await conn.fetchval(
                """
                INSERT INTO public.dpo_dataset (
                    feedback_id, company_id, ship_type, prompt, chosen, rejected, status, dataset_version, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, 'pending_training', $7, now(), now())
                RETURNING dpo_id
                """,
                feedback_id,
                company_id,
                ship_type,
                prompt.strip(),
                chosen.strip(),
                rejected.strip(),
                dataset_version,
            )
            logger.info("Appended DPO preference pair (dpo_id={})", dpo_id)
            return dpo_id

    async def export_dataset(
        self,
        company_id: Optional[str] = None,
        dataset_version: Optional[str] = None,
        status: Optional[str] = None,
        format_type: str = "jsonl",
    ) -> List[Dict[str, Any]]:
        """
        Exports DPO preference pairs in standard format (prompt, chosen, rejected).
        """
        query = "SELECT dpo_id, feedback_id, company_id, ship_type, prompt, chosen, rejected, status, dataset_version, created_at FROM public.dpo_dataset WHERE 1=1"
        params: List[Any] = []

        if company_id:
            params.append(company_id)
            query += f" AND company_id = ${len(params)}"

        if dataset_version:
            params.append(dataset_version)
            query += f" AND dataset_version = ${len(params)}"

        if status:
            params.append(status)
            query += f" AND status = ${len(params)}"

        query += " ORDER BY dpo_id ASC"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            dataset = []
            for r in rows:
                dataset.append({
                    "dpo_id": r["dpo_id"],
                    "feedback_id": r["feedback_id"],
                    "company_id": r["company_id"],
                    "ship_type": r["ship_type"],
                    "prompt": r["prompt"],
                    "chosen": r["chosen"],
                    "rejected": r["rejected"],
                    "status": r["status"],
                    "dataset_version": r["dataset_version"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                })
            return dataset

    async def create_training_job(
        self,
        company_id: Optional[str] = None,
        dataset_version: str = "v1.0",
        base_model: str = "gpt-4o-mini",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compiles dataset count and enqueues a fine-tuning training job.
        """
        job_id = f"dpo_job_{uuid.uuid4().hex[:12]}"

        async with self.pool.acquire() as conn:
            count_query = "SELECT count(*) FROM public.dpo_dataset WHERE 1=1"
            params: List[Any] = []
            if company_id:
                params.append(company_id)
                count_query += f" AND company_id = ${len(params)}"
            if dataset_version:
                params.append(dataset_version)
                count_query += f" AND dataset_version = ${len(params)}"

            example_count = await conn.fetchval(count_query, *params) or 0

            metadata = {
                "notes": notes or "Automated DPO continuous fine-tuning batch",
                "triggered_by": "admin",
            }

            await conn.execute(
                """
                INSERT INTO public.dpo_training_jobs (
                    job_id, company_id, dataset_version, example_count, base_model,
                    status, metadata, started_at, created_at
                )
                VALUES ($1, $2, $3, $4, $5, 'queued', $6::jsonb, now(), now())
                """,
                job_id,
                company_id,
                dataset_version,
                example_count,
                base_model,
                json.dumps(metadata),
            )

            # Mark dataset items as in_training or scheduled
            if example_count > 0:
                await conn.execute(
                    """
                    UPDATE public.dpo_dataset
                    SET status = 'in_training', updated_at = now()
                    WHERE status = 'pending_training'
                    """
                )

            logger.info("Enqueued DPO training job {} with {} examples", job_id, example_count)
            return {
                "job_id": job_id,
                "company_id": company_id,
                "dataset_version": dataset_version,
                "example_count": example_count,
                "base_model": base_model,
                "status": "queued",
                "metadata": metadata,
            }

    async def list_training_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Lists recent DPO training jobs."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT job_id, company_id, dataset_version, example_count, base_model,
                       output_model, status, error_message, started_at, completed_at, metadata, created_at
                FROM public.dpo_training_jobs
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
            jobs = []
            for r in rows:
                raw_meta = r["metadata"]
                meta_dict = json.loads(raw_meta) if isinstance(raw_meta, str) else (raw_meta or {})
                jobs.append({
                    "job_id": r["job_id"],
                    "company_id": r["company_id"],
                    "dataset_version": r["dataset_version"],
                    "example_count": r["example_count"],
                    "base_model": r["base_model"],
                    "output_model": r["output_model"],
                    "status": r["status"],
                    "error_message": r["error_message"],
                    "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                    "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
                    "metadata": meta_dict,
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                })
            return jobs

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        output_model: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Updates the status and output model of a DPO training job."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE public.dpo_training_jobs
                SET status = $1, output_model = $2, error_message = $3, completed_at = now()
                WHERE job_id = $4
                """,
                status,
                output_model,
                error_message,
                job_id,
            )
            return True
