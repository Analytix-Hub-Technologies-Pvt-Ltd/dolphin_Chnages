from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from asyncpg import Pool
from fastapi import HTTPException
from loguru import logger

from models.feedback_models import FeedbackSubmitRequest
from services.feedback_memory_service import FeedbackMemoryService
from services.dpo_service import DPOService
from services.openai_service import OpenAIService

FEEDBACK_CATEGORY_LABELS: Dict[str, str] = {
    "incorrect_information": "Incorrect information",
    "did_not_answer_question": "Didn't answer my question",
    "irrelevant_answer": "Irrelevant answer",
    "incomplete_answer": "Incomplete answer",
    "does_not_match_procedure": "Doesn't match company procedure",
    "other": "Other",
}


class FeedbackService:
    def __init__(
        self,
        pool: Pool,
        memory_service: FeedbackMemoryService,
        dpo_service: DPOService,
        openai_service: Optional[OpenAIService] = None,
    ) -> None:
        self.pool = pool
        self.memory_service = memory_service
        self.dpo_service = dpo_service
        self.openai_service = openai_service or OpenAIService()

    async def submit_feedback(self, payload: FeedbackSubmitRequest) -> Dict[str, Any]:
        """
        Submit user feedback:
        - If feedback_type is 'positive', store as positive.
        - Otherwise, store as 'pending' for administrator review.
        """
        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
        is_positive = (payload.feedback_type or "").strip().lower() == "positive"
        status = "positive" if is_positive else "pending"

        query = """
        INSERT INTO public.feedback_records (
            feedback_id, user_id, conversation_id, message_id,
            question, original_response, feedback_type, feedback_comment,
            company_id, ship_type, source_metadata, status,
            created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4,
            $5, $6, $7, $8,
            $9, $10, $11::jsonb, $12,
            now(), now()
        )
        RETURNING *;
        """

        metadata_json = json.dumps(payload.source_metadata or {})
        comp_id = str(payload.company_id).strip() if payload.company_id else None
        st = str(payload.ship_type).strip() if payload.ship_type else None

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                feedback_id,
                payload.user_id or "anonymous",
                payload.conversation_id,
                payload.message_id,
                payload.question,
                payload.original_response,
                payload.feedback_type,
                payload.feedback_comment,
                comp_id,
                st,
                metadata_json,
                status,
            )
            logger.info(
                f"📝 [FeedbackService] Saved {status} feedback '{feedback_id}' "
                f"(Type: '{payload.feedback_type}', Company: '{comp_id}')"
            )
            return dict(row) if row else {}

    async def get_feedback_stats(self, company_id: Optional[str] = None) -> Dict[str, int]:
        """Get dynamic feedback badge statistics."""
        comp_id = str(company_id).strip() if company_id else None

        query = """
        SELECT
            COUNT(*) FILTER (WHERE status = 'pending') AS pending_count,
            COUNT(*) FILTER (WHERE status = 'approved') AS approved_count,
            COUNT(*) FILTER (WHERE status = 'rejected') AS rejected_count,
            COUNT(*) AS total_count
        FROM public.feedback_records
        WHERE ($1::text IS NULL OR company_id = $1);
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, comp_id)
            if row:
                return {
                    "pending_count": row["pending_count"] or 0,
                    "approved_count": row["approved_count"] or 0,
                    "rejected_count": row["rejected_count"] or 0,
                    "total_count": row["total_count"] or 0,
                }
            return {"pending_count": 0, "approved_count": 0, "rejected_count": 0, "total_count": 0}

    async def list_pending_feedback(
        self,
        company_id: Optional[str] = None,
        search: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List pending feedback items with search and pagination."""
        comp_id = str(company_id).strip() if company_id else None
        search_pattern = f"%{search.strip()}%" if search.strip() else None

        query = """
        SELECT *
        FROM public.feedback_records
        WHERE status = 'pending'
          AND ($1::text IS NULL OR company_id = $1)
          AND (
            $2::text IS NULL
            OR question ILIKE $2
            OR feedback_comment ILIKE $2
            OR feedback_id ILIKE $2
            OR feedback_type ILIKE $2
          )
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4;
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, comp_id, search_pattern, limit, offset)
            return [dict(r) for r in rows]

    async def list_approved_feedback(
        self,
        company_id: Optional[str] = None,
        search: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List approved feedback items with search and pagination."""
        comp_id = str(company_id).strip() if company_id else None
        search_pattern = f"%{search.strip()}%" if search.strip() else None

        query = """
        SELECT *
        FROM public.feedback_records
        WHERE status = 'approved'
          AND ($1::text IS NULL OR company_id = $1)
          AND (
            $2::text IS NULL
            OR question ILIKE $2
            OR preferred_response ILIKE $2
            OR original_response ILIKE $2
            OR feedback_id ILIKE $2
            OR reviewed_by ILIKE $2
          )
        ORDER BY reviewed_at DESC NULLS LAST, created_at DESC
        LIMIT $3 OFFSET $4;
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, comp_id, search_pattern, limit, offset)
            return [dict(r) for r in rows]

    async def get_feedback_by_id(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """Get single feedback item by ID."""
        query = "SELECT * FROM public.feedback_records WHERE feedback_id = $1;"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, feedback_id)
            return dict(row) if row else None

    async def approve_feedback(
        self,
        feedback_id: str,
        preferred_response: str,
        question: Optional[str] = None,
        reviewer_id: str = "admin",
        admin_comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Approve feedback:
        1. Validate preferred_response is not empty.
        2. Update feedback status to 'approved', store reviewer metadata.
        3. Index in approved feedback vector memory for instant RAG boost.
        4. Add to DPO training dataset (prompt, chosen, rejected).
        5. ⚡ AUTOMATICALLY trigger background DPO training job.
        """
        clean_preferred = (preferred_response or "").strip()
        if not clean_preferred:
            raise HTTPException(status_code=400, detail="Preferred response cannot be empty for approval.")

        fetch_query = "SELECT * FROM public.feedback_records WHERE feedback_id = $1;"
        async with self.pool.acquire() as conn:
            existing = await conn.fetchrow(fetch_query, feedback_id)
            if not existing:
                raise HTTPException(status_code=404, detail="Feedback record not found.")

            clean_q = question.strip() if question and question.strip() else existing["question"]

            update_query = """
            UPDATE public.feedback_records
            SET status = 'approved',
                question = $2,
                preferred_response = $3,
                reviewed_by = $4,
                reviewed_at = now(),
                admin_comment = $5,
                rejection_reason = NULL,
                updated_at = now()
            WHERE feedback_id = $1
            RETURNING *;
            """
            updated_row = await conn.fetchrow(
                update_query,
                feedback_id,
                clean_q,
                clean_preferred,
                reviewer_id or "admin",
                admin_comment,
            )
            feedback_data = dict(updated_row)

        # 3. Create approved vector memory (instant semantic match in RAG)
        try:
            await self.memory_service.save_approved_memory(
                feedback_id=feedback_id,
                question=feedback_data["question"],
                preferred_response=clean_preferred,
                original_response=feedback_data["original_response"],
                company_id=feedback_data["company_id"],
                ship_type=feedback_data["ship_type"],
                approved_by=reviewer_id or "admin",
            )
        except Exception as mem_err:
            logger.error(f"Failed to index feedback memory: {mem_err}")

        # 4. Add to DPO dataset
        try:
            await self.dpo_service.add_dataset_example(
                feedback_id=feedback_id,
                prompt=feedback_data["question"],
                chosen=clean_preferred,
                rejected=feedback_data["original_response"],
                company_id=feedback_data["company_id"],
                ship_type=feedback_data["ship_type"],
            )
        except Exception as dpo_err:
            logger.error(f"Failed to add DPO dataset example: {dpo_err}")

        # 5. Automatically trigger background DPO training
        try:
            await self.dpo_service.create_and_run_training_job(
                company_id=feedback_data.get("company_id"),
                base_model="gpt-4o-mini",
                dataset_version="v1.0",
            )
            logger.info(f"⚡ [FeedbackService] Automatically triggered DPO training on approval of '{feedback_id}'")
        except Exception as job_err:
            logger.error(f"Failed to trigger auto DPO training: {job_err}")

        return feedback_data

    async def update_approved_feedback(
        self,
        feedback_id: str,
        preferred_response: str,
        question: Optional[str] = None,
        reviewer_id: str = "admin",
        admin_comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing approved feedback response and refresh its vector memory immediately."""
        return await self.approve_feedback(
            feedback_id=feedback_id,
            preferred_response=preferred_response,
            question=question,
            reviewer_id=reviewer_id,
            admin_comment=admin_comment,
        )

    async def delete_approved_feedback(
        self,
        feedback_id: str,
    ) -> Dict[str, Any]:
        """Delete an approved feedback record and purge it from vector memory."""
        await self.memory_service.remove_approved_memory(feedback_id)
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM public.dpo_dataset WHERE feedback_id = $1;", feedback_id)
            await conn.execute("DELETE FROM public.feedback_records WHERE feedback_id = $1;", feedback_id)
        logger.info(f"🗑️ [FeedbackService] Deleted approved feedback record and memory for '{feedback_id}'")
        return {"status": "deleted", "feedback_id": feedback_id}

    async def reject_feedback(
        self,
        feedback_id: str,
        rejection_reason: str,
        reviewer_id: str = "admin",
    ) -> Dict[str, Any]:
        """
        Reject feedback:
        1. Validate mandatory non-empty rejection reason.
        2. Set status to 'rejected', store reason and reviewer metadata.
        3. Remove from memory and DPO dataset if previously approved.
        """
        clean_reason = (rejection_reason or "").strip()
        if not clean_reason:
            raise HTTPException(status_code=400, detail="Rejection reason is mandatory.")

        fetch_query = "SELECT * FROM public.feedback_records WHERE feedback_id = $1;"
        async with self.pool.acquire() as conn:
            existing = await conn.fetchrow(fetch_query, feedback_id)
            if not existing:
                raise HTTPException(status_code=404, detail="Feedback record not found.")

            update_query = """
            UPDATE public.feedback_records
            SET status = 'rejected',
                rejection_reason = $2,
                reviewed_by = $3,
                reviewed_at = now(),
                updated_at = now()
            WHERE feedback_id = $1
            RETURNING *;
            """
            updated_row = await conn.fetchrow(
                update_query,
                feedback_id,
                clean_reason,
                reviewer_id or "admin",
            )
            feedback_data = dict(updated_row)

        # Cleanup memory and DPO
        await self.memory_service.remove_approved_memory(feedback_id)
        await self.dpo_service.remove_dataset_example(feedback_id)

        logger.info(f"🚫 [FeedbackService] Feedback '{feedback_id}' rejected by '{reviewer_id}': {clean_reason}")
        return feedback_data

    async def regenerate_preferred_response(
        self,
        feedback_id: str,
        topic: str,
        reference_text: Optional[str] = None,
        reviewer_instructions: Optional[str] = None,
        company_id: Optional[str] = None,
        ship_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes an authoritative preferred response for a feedback item based on:
        - The original user question
        - Admin-provided Topic / SOP name / Reference keywords
        - Admin-provided reference text / manual excerpt / guidelines (optional)
        - Relevant company document snippets / chunks from the database
        """
        clean_topic = (topic or "").strip()
        if not clean_topic:
            raise HTTPException(status_code=400, detail="Topic or reference is required for AI response generation.")

        # 1. Fetch feedback record
        feedback_item = await self.get_feedback_by_id(feedback_id)
        if not feedback_item:
            raise HTTPException(status_code=404, detail="Feedback record not found.")

        question = feedback_item.get("question", "")
        effective_company_id = company_id or feedback_item.get("company_id")
        effective_ship_type = ship_type or feedback_item.get("ship_type")
        original_response = feedback_item.get("original_response", "")

        # 2. Search related company documents and course content
        matched_chunks = []
        search_terms = [t for t in re.split(r"\s+", clean_topic) if len(t) > 2][:5]

        # 2a. Query company_documents if company_id is available
        if effective_company_id and search_terms:
            try:
                conditions = []
                for idx, term in enumerate(search_terms, start=2):
                    conditions.append(f"content ILIKE ${idx} OR topic ILIKE ${idx} OR document_name ILIKE ${idx}")
                query_filter = " OR ".join(conditions)

                doc_query = f"""
                SELECT document_name, topic, content
                FROM public.company_documents
                WHERE ($1::text IS NULL OR company_id = $1)
                  AND ({query_filter})
                LIMIT 4;
                """
                async with self.pool.acquire() as conn:
                    params = [str(effective_company_id)] + [f"%{term}%" for term in search_terms]
                    rows = await conn.fetch(doc_query, *params)
                    for r in rows:
                        matched_chunks.append(f"Company SMS Document: {r['document_name']} | Topic: {r['topic']}\n{r['content']}")
            except Exception as e:
                logger.warning(f"Failed to query company_documents for feedback regeneration: {e}")

        # 2b. Query course_content for matching curriculum topics
        if search_terms:
            try:
                c_conditions = []
                for idx, term in enumerate(search_terms, start=1):
                    c_conditions.append(f"topic_name ILIKE ${idx} OR topic_content ILIKE ${idx} OR topic_code ILIKE ${idx} OR course_code ILIKE ${idx}")
                c_filter = " OR ".join(c_conditions)

                course_query = f"""
                SELECT course_code, topic_code, topic_name, topic_content
                FROM public.course_content
                WHERE {c_filter}
                LIMIT 4;
                """
                async with self.pool.acquire() as conn:
                    c_params = [f"%{term}%" for term in search_terms]
                    c_rows = await conn.fetch(course_query, *c_params)
                    for r in c_rows:
                        raw_snip = (r["topic_content"] or "").strip()
                        snip = raw_snip[:1500] if len(raw_snip) > 1500 else raw_snip
                        if snip:
                            matched_chunks.append(
                                f"Course Curriculum: {r['course_code']} - {r['topic_name']} ({r['topic_code']})\n{snip}"
                            )
            except Exception as ce:
                logger.warning(f"Failed to query course_content for feedback regeneration: {ce}")

        # 3. Construct prompt
        system_prompt = (
            "You are Marine Tutor AI and the Senior HSQE Superintendent / Maritime Technical Authority for Dolphin AI.\n"
            "An administrator/SME is reviewing a user feedback ticket where the original AI response was flagged as irrelevant or incorrect.\n"
            "Your task is to generate a comprehensive, fully detailed, authoritative, professional maritime response that directly answers the user's question, strictly grounded in the provided topic, manual reference, and guidelines.\n\n"
            "CRITICAL FORMAT & QUALITY RULES:\n"
            "1. FULL PROCEDURAL COMPLETENESS: Never provide brief summaries or placeholders. Provide complete step-by-step procedures, safety precautions, hazard controls, equipment checks, and regulatory standards.\n"
            "2. STRUCTURED SECTIONS: Use clear Markdown headings (`###`, `####`), bold parameters, and numbered lists.\n"
            "3. TABLES & CHECKLISTS: Whenever relevant to procedures, permits, PPE, or responsibilities, output clean Markdown tables (e.g. `| Step | Action | Responsibility | Precautions |`).\n"
            "4. REGULATORY & SAFETY STANDARDS: Align with SOLAS, MARPOL, STCW, and company SMS/QMS procedures.\n"
            "5. TONE: Authoritative, clear, precise, and directly usable by shipboard officers and crew."
        )

        user_content_parts = [
            f"### ORIGINAL USER QUESTION:\n{question}",
            f"### ADMIN SPECIFIED TOPIC / SOP REFERENCE:\n{clean_topic}",
        ]

        if effective_company_id:
            user_content_parts.append(f"### COMPANY CONTEXT:\nCompany: {effective_company_id}\nShip Type: {effective_ship_type or 'General Vessel'}")

        if reference_text and reference_text.strip():
            user_content_parts.append(f"### ADMIN REFERENCE EXCERPT / MANUAL TEXT / GUIDELINES:\n{reference_text.strip()}")

        if matched_chunks:
            user_content_parts.append("### RELEVANT COMPANY SMS KNOWLEDGE BASE CHUNKS:\n" + "\n\n---\n\n".join(matched_chunks))

        if reviewer_instructions and reviewer_instructions.strip():
            user_content_parts.append(f"### ADDITIONAL REVIEWER INSTRUCTIONS:\n{reviewer_instructions.strip()}")

        user_content_parts.append(
            "Please generate the complete, authoritative preferred response in clean Markdown format ready to be approved into the system memory and training dataset."
        )

        user_prompt = "\n\n".join(user_content_parts)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(f"🤖 [FeedbackService] Generating preferred response for feedback '{feedback_id}' on topic '{clean_topic}'")
        generated_response = await self.openai_service.chat(
            messages=messages,
            temperature=0.2,
            category="FEEDBACK_REGENERATION",
        )

        return {
            "feedback_id": feedback_id,
            "topic": clean_topic,
            "generated_response": (generated_response or "").strip(),
            "status": "success",
            "reference_text_used": bool(reference_text and reference_text.strip()),
        }

    async def get_dashboard_analytics(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        date_range: Optional[str] = "30d",
        company_id: Optional[str] = None,
        ship_type: Optional[str] = None,
        status: Optional[str] = None,
        feedback_type: Optional[str] = None,
        reviewer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Aggregated backend analytics for the Feedback Dashboard.
        Performs optimized database-level queries with strict company isolation.
        """
        now = datetime.now(timezone.utc)
        from_dt: Optional[datetime] = None
        to_dt: Optional[datetime] = None

        if date_range:
            dr = date_range.lower().strip()
            if dr in ("today", "1d"):
                from_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif dr in ("7d", "last 7 days", "last_7_days", "7_days"):
                from_dt = now - timedelta(days=7)
            elif dr in ("30d", "last 30 days", "last_30_days", "30_days"):
                from_dt = now - timedelta(days=30)
            elif dr in ("90d", "last 90 days", "last_90_days", "90_days"):
                from_dt = now - timedelta(days=90)
            elif dr in ("custom", "custom_range"):
                if from_date:
                    try:
                        from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
                    except Exception:
                        pass
                if to_date:
                    try:
                        to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
                    except Exception:
                        pass
        elif from_date or to_date:
            if from_date:
                try:
                    from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
                except Exception:
                    pass
            if to_date:
                try:
                    to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
                except Exception:
                    pass
        else:
            from_dt = now - timedelta(days=30)

        # Build parameterized where conditions
        conditions: List[str] = []
        params: List[Any] = []
        idx = 1

        if company_id and company_id.strip() and company_id.strip().lower() != "all":
            conditions.append(f"company_id = ${idx}")
            params.append(company_id.strip())
            idx += 1

        if ship_type and ship_type.strip() and ship_type.strip().lower() != "all":
            conditions.append(f"ship_type = ${idx}")
            params.append(ship_type.strip())
            idx += 1

        if status and status.strip() and status.strip().lower() != "all":
            st_val = status.strip().lower()
            if st_val == "positive":
                conditions.append("(status = 'positive' OR feedback_type = 'positive')")
            elif st_val in ("pending", "approved", "rejected"):
                conditions.append(f"status = ${idx}")
                params.append(st_val)
                idx += 1

        if feedback_type and feedback_type.strip() and feedback_type.strip().lower() != "all":
            conditions.append(f"feedback_type = ${idx}")
            params.append(feedback_type.strip())
            idx += 1

        if reviewer_id and reviewer_id.strip() and reviewer_id.strip().lower() != "all":
            conditions.append(f"reviewed_by = ${idx}")
            params.append(reviewer_id.strip())
            idx += 1

        if from_dt:
            conditions.append(f"created_at >= ${idx}")
            params.append(from_dt)
            idx += 1

        if to_dt:
            conditions.append(f"created_at <= ${idx}")
            params.append(to_dt)
            idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        async with self.pool.acquire() as conn:
            # 1. Summary Metrics
            summary_query = f"""
            SELECT
                COUNT(*) AS total_count,
                COUNT(*) FILTER (WHERE feedback_type = 'positive' OR status = 'positive') AS positive_count,
                COUNT(*) FILTER (WHERE feedback_type != 'positive' AND status != 'positive') AS negative_count,
                COUNT(*) FILTER (WHERE status = 'pending') AS pending_count,
                COUNT(*) FILTER (WHERE status = 'approved') AS approved_count,
                COUNT(*) FILTER (WHERE status = 'rejected') AS rejected_count
            FROM public.feedback_records
            {where_clause};
            """
            sum_row = await conn.fetchrow(summary_query, *params)
            pos_fb = int(sum_row["positive_count"] or 0) if sum_row else 0
            neg_fb = int(sum_row["negative_count"] or 0) if sum_row else 0
            pend_fb = int(sum_row["pending_count"] or 0) if sum_row else 0
            app_fb = int(sum_row["approved_count"] or 0) if sum_row else 0
            rej_fb = int(sum_row["rejected_count"] or 0) if sum_row else 0
            total_fb = pos_fb + neg_fb
            satisfaction_rate = round((pos_fb / total_fb) * 100.0, 1) if total_fb > 0 else None

            summary_data = {
                "total_feedback": total_fb,
                "positive_feedback": pos_fb,
                "negative_feedback": neg_fb,
                "pending_issues": pend_fb,
                "approved_issues": app_fb,
                "rejected_issues": rej_fb,
                "satisfaction_rate": satisfaction_rate,
            }

            # 2. Feedback Trend
            trend_query = f"""
            SELECT
                to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS day_str,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE feedback_type = 'positive' OR status = 'positive') AS positive,
                COUNT(*) FILTER (WHERE feedback_type != 'positive' AND status != 'positive') AS negative
            FROM public.feedback_records
            {where_clause}
            GROUP BY 1
            ORDER BY 1 ASC;
            """
            trend_rows = await conn.fetch(trend_query, *params)
            trend_data = [
                {
                    "date": r["day_str"],
                    "total": int(r["total"] or 0),
                    "positive": int(r["positive"] or 0),
                    "negative": int(r["negative"] or 0),
                }
                for r in trend_rows
                if r["day_str"]
            ]

            # 3. Issue Category Breakdown
            cat_where_prefix = "AND" if where_clause else "WHERE"
            cat_query = f"""
            SELECT
                feedback_type,
                COUNT(*) AS count
            FROM public.feedback_records
            {where_clause}
            {cat_where_prefix} (feedback_type != 'positive' AND status != 'positive')
            GROUP BY feedback_type
            ORDER BY count DESC;
            """
            cat_rows = await conn.fetch(cat_query, *params)
            cat_counts = {r["feedback_type"]: int(r["count"] or 0) for r in cat_rows}

            # Ensure all standard categories appear in structured output
            categories_data = []
            seen_categories = set()
            for cat_id, cat_label in FEEDBACK_CATEGORY_LABELS.items():
                seen_categories.add(cat_id)
                count = cat_counts.get(cat_id, 0)
                pct = round((count / neg_fb) * 100.0, 1) if neg_fb > 0 else 0.0
                categories_data.append({
                    "id": cat_id,
                    "label": cat_label,
                    "count": count,
                    "percentage": pct,
                })

            for cat_id, count in cat_counts.items():
                if cat_id not in seen_categories and cat_id not in ("positive", "none", None):
                    pct = round((count / neg_fb) * 100.0, 1) if neg_fb > 0 else 0.0
                    categories_data.append({
                        "id": cat_id,
                        "label": cat_id.replace("_", " ").capitalize(),
                        "count": count,
                        "percentage": pct,
                    })

            # Sort categories by count descending
            categories_data.sort(key=lambda x: x["count"], reverse=True)

            # 4. Resolution Status Distribution
            res_where_prefix = "AND" if where_clause else "WHERE"
            res_query = f"""
            SELECT
                status,
                COUNT(*) AS count
            FROM public.feedback_records
            {where_clause}
            {res_where_prefix} status IN ('pending', 'approved', 'rejected')
            GROUP BY status;
            """
            res_rows = await conn.fetch(res_query, *params)
            res_counts = {r["status"]: int(r["count"] or 0) for r in res_rows}
            total_res = sum(res_counts.values())

            resolution_status_data = [
                {
                    "status": "pending",
                    "label": "Pending Review",
                    "count": res_counts.get("pending", 0),
                    "percentage": round((res_counts.get("pending", 0) / total_res) * 100.0, 1) if total_res > 0 else 0.0,
                },
                {
                    "status": "approved",
                    "label": "Approved (Memory & DPO)",
                    "count": res_counts.get("approved", 0),
                    "percentage": round((res_counts.get("approved", 0) / total_res) * 100.0, 1) if total_res > 0 else 0.0,
                },
                {
                    "status": "rejected",
                    "label": "Rejected",
                    "count": res_counts.get("rejected", 0),
                    "percentage": round((res_counts.get("rejected", 0) / total_res) * 100.0, 1) if total_res > 0 else 0.0,
                },
            ]

            # 5. Total Issues Resolved by SMEs / Admins
            rev_where_prefix = "AND" if where_clause else "WHERE"
            rev_query = f"""
            SELECT
                COALESCE(NULLIF(TRIM(reviewed_by), ''), 'Unknown Reviewer') AS reviewer,
                COUNT(*) FILTER (WHERE status = 'approved') AS approved_count,
                COUNT(*) FILTER (WHERE status = 'rejected') AS rejected_count,
                COUNT(*) AS total_resolved
            FROM public.feedback_records
            {where_clause}
            {rev_where_prefix} status IN ('approved', 'rejected')
            GROUP BY 1
            ORDER BY total_resolved DESC, approved_count DESC
            LIMIT 50;
            """
            rev_rows = await conn.fetch(rev_query, *params)
            reviewer_resolution_data = [
                {
                    "reviewer": r["reviewer"],
                    "approved": int(r["approved_count"] or 0),
                    "rejected": int(r["rejected_count"] or 0),
                    "total_resolved": int(r["total_resolved"] or 0),
                }
                for r in rev_rows
            ]

            # 6. Pending Issue Aging
            aging_where_prefix = "AND" if where_clause else "WHERE"
            aging_query = f"""
            SELECT
                COUNT(*) FILTER (WHERE now() - created_at < interval '4 hours') AS under_4h,
                COUNT(*) FILTER (WHERE now() - created_at >= interval '4 hours' AND now() - created_at < interval '24 hours') AS h4_to_24h,
                COUNT(*) FILTER (WHERE now() - created_at >= interval '24 hours' AND now() - created_at < interval '72 hours') AS d1_to_3d,
                COUNT(*) FILTER (WHERE now() - created_at >= interval '72 hours') AS over_3d
            FROM public.feedback_records
            {where_clause}
            {aging_where_prefix} status = 'pending';
            """
            aging_row = await conn.fetchrow(aging_query, *params)
            aging_data = [
                {"bucket": "< 4 hours", "count": int(aging_row["under_4h"] or 0) if aging_row else 0, "is_oldest": False},
                {"bucket": "4–24 hours", "count": int(aging_row["h4_to_24h"] or 0) if aging_row else 0, "is_oldest": False},
                {"bucket": "1–3 days", "count": int(aging_row["d1_to_3d"] or 0) if aging_row else 0, "is_oldest": False},
                {"bucket": "> 3 days", "count": int(aging_row["over_3d"] or 0) if aging_row else 0, "is_oldest": True},
            ]

            # 7. Recent Feedback Activity (Latest 10 records)
            recent_query = f"""
            SELECT *
            FROM public.feedback_records
            {where_clause}
            ORDER BY created_at DESC
            LIMIT 10;
            """
            recent_rows = await conn.fetch(recent_query, *params)
            recent_data = [dict(r) for r in recent_rows]

            # 8. Company-Wise Analytics
            comp_query = f"""
            SELECT
                COALESCE(NULLIF(TRIM(company_id), ''), 'Global') AS comp_name,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE feedback_type = 'positive' OR status = 'positive') AS positive,
                COUNT(*) FILTER (WHERE feedback_type != 'positive' AND status != 'positive') AS negative,
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE status = 'approved') AS approved
            FROM public.feedback_records
            {where_clause}
            GROUP BY 1
            ORDER BY total DESC;
            """
            comp_rows = await conn.fetch(comp_query, *params)
            company_summary_data = []
            for r in comp_rows:
                c_pos = int(r["positive"] or 0)
                c_neg = int(r["negative"] or 0)
                c_total = c_pos + c_neg
                c_sat = round((c_pos / c_total) * 100.0, 1) if c_total > 0 else None
                company_summary_data.append({
                    "company_id": r["comp_name"],
                    "total": int(r["total"] or 0),
                    "positive": c_pos,
                    "negative": c_neg,
                    "pending": int(r["pending"] or 0),
                    "approved": int(r["approved"] or 0),
                    "satisfaction_rate": c_sat,
                })

            # 9. Ship Type Analytics
            ship_where_prefix = "AND" if where_clause else "WHERE"
            ship_query = f"""
            SELECT
                ship_type,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE feedback_type = 'positive' OR status = 'positive') AS positive,
                COUNT(*) FILTER (WHERE feedback_type != 'positive' AND status != 'positive') AS negative,
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE status = 'approved') AS approved
            FROM public.feedback_records
            {where_clause}
            {ship_where_prefix} ship_type IS NOT NULL AND TRIM(ship_type) != ''
            GROUP BY ship_type
            ORDER BY total DESC;
            """
            ship_rows = await conn.fetch(ship_query, *params)
            ship_type_summary_data = []
            for r in ship_rows:
                s_pos = int(r["positive"] or 0)
                s_neg = int(r["negative"] or 0)
                s_total = s_pos + s_neg
                s_sat = round((s_pos / s_total) * 100.0, 1) if s_total > 0 else None
                ship_type_summary_data.append({
                    "ship_type": r["ship_type"],
                    "total": int(r["total"] or 0),
                    "positive": s_pos,
                    "negative": s_neg,
                    "pending": int(r["pending"] or 0),
                    "approved": int(r["approved"] or 0),
                    "satisfaction_rate": s_sat,
                })

            # 10. Filter Options (companies, ship types, reviewers)
            opts_query = """
            SELECT
                ARRAY(SELECT DISTINCT company_id FROM public.feedback_records WHERE company_id IS NOT NULL AND TRIM(company_id) != '' ORDER BY 1) AS companies,
                ARRAY(SELECT DISTINCT ship_type FROM public.feedback_records WHERE ship_type IS NOT NULL AND TRIM(ship_type) != '' ORDER BY 1) AS ship_types,
                ARRAY(SELECT DISTINCT reviewed_by FROM public.feedback_records WHERE reviewed_by IS NOT NULL AND TRIM(reviewed_by) != '' ORDER BY 1) AS reviewers;
            """
            opts_row = await conn.fetchrow(opts_query)
            filter_options = {
                "companies": list(opts_row["companies"] or []) if opts_row else [],
                "ship_types": list(opts_row["ship_types"] or []) if opts_row else [],
                "reviewers": list(opts_row["reviewers"] or []) if opts_row else [],
                "categories": list(FEEDBACK_CATEGORY_LABELS.keys()),
            }

            return {
                "summary": summary_data,
                "trend": trend_data,
                "categories": categories_data,
                "resolution_status": resolution_status_data,
                "reviewer_resolution": reviewer_resolution_data,
                "aging": aging_data,
                "recent_feedback": recent_data,
                "company_summary": company_summary_data,
                "ship_type_summary": ship_type_summary_data,
                "filter_options": filter_options,
            }

