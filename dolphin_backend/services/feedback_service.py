from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from asyncpg import Pool
from loguru import logger

from models.feedback_models import (
    FeedbackAgingBucket,
    FeedbackCategoryCount,
    FeedbackCompanySummary,
    FeedbackCountsResponse,
    FeedbackCreateRequest,
    FeedbackDashboardResponse,
    FeedbackItem,
    FeedbackReviewRequest,
    FeedbackShipTypeSummary,
    FeedbackSmeResolution,
    FeedbackStatusCount,
    FeedbackSummary,
    FeedbackTrendItem,
    PaginatedFeedbackResponse,
)

STANDARD_CATEGORIES = [
    "Incorrect information",
    "Didn't answer my question",
    "Irrelevant answer",
    "Incomplete answer",
    "Doesn't match company procedure",
    "Other",
]


_table_initialized = False


class FeedbackService:
    def __init__(
        self,
        pool: Pool,
        memory_service: Any = None,
        dpo_service: Any = None,
        openai_service: Any = None,
    ) -> None:
        self.pool = pool
        self.memory_service = memory_service
        self.dpo_service = dpo_service
        self.openai_service = openai_service

    async def init_table(self) -> None:
        """Create feedback table and necessary indexes if they do not exist."""
        global _table_initialized
        if _table_initialized:
            return
        query = """
        CREATE TABLE IF NOT EXISTS public.feedback (
            feedback_id BIGSERIAL PRIMARY KEY,
            user_id TEXT DEFAULT 'anonymous',
            user_name TEXT,
            session_id TEXT,
            conversation_id TEXT,
            message_id INTEGER,
            question TEXT,
            original_response TEXT,
            edited_response TEXT,
            feedback_type TEXT NOT NULL, -- 'positive' or 'negative'
            rating TEXT,                 -- 'positive' or 'negative'
            category TEXT,               -- category for negative feedback
            comment TEXT,
            company_id TEXT,
            company_name TEXT,
            ship_type TEXT,
            model_version TEXT DEFAULT 'dolphin-v1',
            status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
            reviewed_by TEXT,
            reviewed_by_name TEXT,
            reviewer_notes TEXT,
            resolution_action TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMPTZ
        );

        CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON public.feedback (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_feedback_status ON public.feedback (status);
        CREATE INDEX IF NOT EXISTS idx_feedback_type ON public.feedback (feedback_type);
        CREATE INDEX IF NOT EXISTS idx_feedback_company_id ON public.feedback (company_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_ship_type ON public.feedback (ship_type);
        CREATE INDEX IF NOT EXISTS idx_feedback_reviewed_by ON public.feedback (reviewed_by);
        CREATE INDEX IF NOT EXISTS idx_feedback_session_id ON public.feedback (session_id);
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query)
            try:
                cnt = await conn.fetchval("SELECT COUNT(*) FROM public.feedback;")
                if cnt == 0:
                    has_records = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_schema = 'public' AND table_name = 'feedback_records'
                        );
                    """)
                    if has_records:
                        await conn.execute("""
                            INSERT INTO public.feedback (
                                user_id, user_name, session_id, conversation_id,
                                question, original_response, edited_response,
                                feedback_type, rating, category, comment, company_id,
                                ship_type, model_version, status, reviewed_by,
                                reviewer_notes, resolution_action, created_at, updated_at, resolved_at
                            )
                            SELECT 
                                user_id,
                                COALESCE(user_id, 'anonymous'),
                                conversation_id,
                                conversation_id,
                                question,
                                original_response,
                                preferred_response,
                                CASE WHEN LOWER(feedback_type) = 'positive' OR LOWER(status) = 'positive' THEN 'positive' ELSE 'negative' END,
                                CASE WHEN LOWER(feedback_type) = 'positive' OR LOWER(status) = 'positive' THEN 'positive' ELSE 'negative' END,
                                CASE 
                                    WHEN LOWER(feedback_type) = 'incorrect_information' THEN 'Incorrect information'
                                    WHEN LOWER(feedback_type) = 'incomplete_answer' THEN 'Incomplete answer'
                                    WHEN LOWER(feedback_type) = 'did_not_answer_question' THEN 'Didn''t answer my question'
                                    WHEN LOWER(feedback_type) = 'irrelevant_answer' THEN 'Irrelevant answer'
                                    WHEN LOWER(feedback_type) = 'does_not_match_procedure' THEN 'Doesn''t match company procedure'
                                    WHEN LOWER(feedback_type) = 'positive' THEN NULL
                                    ELSE 'Other'
                                END,
                                feedback_comment,
                                company_id,
                                ship_type,
                                'dolphin-v1',
                                CASE 
                                    WHEN LOWER(status) IN ('approved', 'positive') THEN 'approved'
                                    WHEN LOWER(status) IN ('rejected', 'discarded') THEN 'rejected'
                                    ELSE 'pending'
                                END,
                                reviewed_by,
                                COALESCE(admin_comment, rejection_reason),
                                CASE WHEN LOWER(status) IN ('approved', 'positive') THEN 'SME verified and approved' ELSE NULL END,
                                created_at,
                                COALESCE(updated_at, created_at),
                                COALESCE(reviewed_at, updated_at)
                            FROM public.feedback_records;
                        """)
                        logger.info("Migrated legacy feedback records into public.feedback")
            except Exception as e:
                logger.warning(f"Legacy feedback migration check skipped: {e}")
        _table_initialized = True

    def _row_to_item(self, row: Any) -> FeedbackItem:
        edited = row["edited_response"]
        notes = row["reviewer_notes"]
        res_at = row["resolved_at"] or row["updated_at"]
        return FeedbackItem(
            feedback_id=row["feedback_id"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            session_id=row["session_id"],
            conversation_id=row["conversation_id"] or row["session_id"],
            message_id=row["message_id"],
            question=row["question"],
            original_response=row["original_response"],
            edited_response=edited,
            preferred_response=edited or (row["original_response"] if row["status"] == "approved" else None),
            feedback_type=row["feedback_type"],
            category=row["category"],
            comment=row["comment"],
            feedback_comment=row["comment"],
            company_id=str(row["company_id"]) if row["company_id"] is not None else None,
            company_name=row["company_name"],
            ship_type=row["ship_type"],
            model_version=row["model_version"],
            status=row["status"],
            reviewed_by=row["reviewed_by"],
            reviewed_by_name=row["reviewed_by_name"],
            reviewer_notes=notes,
            admin_comment=notes,
            resolution_action=row["resolution_action"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            resolved_at=row["resolved_at"],
            reviewed_at=res_at if row["status"] in ("approved", "rejected") else None,
        )

    async def create_feedback(self, payload: FeedbackCreateRequest) -> FeedbackItem:
        """Create a new feedback record in database."""
        await self.init_table()

        raw_type = (payload.feedback_type or "positive").strip().lower()
        category = payload.category
        comment = payload.comment or payload.feedback_comment

        if raw_type in {"positive", "negative"}:
            feedback_type = raw_type
        else:
            # If a negative category was passed in feedback_type (e.g., 'incorrect_information')
            feedback_type = "negative"
            if not category:
                category = payload.feedback_type

        # Default status: positive is auto-approved, negative goes to pending review
        default_status = "approved" if feedback_type == "positive" else "pending"
        resolved_at = datetime.now(timezone.utc) if feedback_type == "positive" else None

        conv_id = payload.conversation_id or payload.session_id

        query = """
        INSERT INTO public.feedback (
            user_id,
            user_name,
            session_id,
            conversation_id,
            message_id,
            question,
            original_response,
            feedback_type,
            rating,
            category,
            comment,
            company_id,
            company_name,
            ship_type,
            model_version,
            status,
            resolved_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        RETURNING *;
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                payload.user_id,
                payload.user_name,
                payload.session_id,
                conv_id,
                payload.message_id,
                payload.question,
                payload.original_response,
                feedback_type,
                payload.rating or feedback_type,
                category,
                comment,
                str(payload.company_id) if payload.company_id is not None else None,
                payload.company_name,
                payload.ship_type,
                payload.model_version or "dolphin-v1",
                default_status,
                resolved_at,
            )

        logger.info(f"Feedback created: id={row['feedback_id']}, type={feedback_type}, status={default_status}")
        return self._row_to_item(row)

    async def delete_feedback(self, feedback_id: int) -> bool:
        """Permanently delete a feedback record from the database."""
        await self.init_table()
        query = "DELETE FROM public.feedback WHERE feedback_id = $1 RETURNING feedback_id;"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, feedback_id)
            if row and self.memory_service:
                try:
                    await self.memory_service.remove_approved_memory(str(feedback_id))
                except Exception as e:
                    logger.warning(f"Could not remove memory for feedback {feedback_id}: {e}")
            return bool(row)

    async def delete_feedback_by_message(
        self, session_id: str, message_id: int, user_id: Optional[str] = None
    ) -> bool:
        """Delete feedback records associated with a specific session and message."""
        await self.init_table()
        if user_id and user_id != "anonymous":
            query = """
            DELETE FROM public.feedback
            WHERE (session_id = $1 OR conversation_id = $1)
              AND message_id = $2
              AND user_id = $3
            RETURNING feedback_id;
            """
            params = [session_id, message_id, user_id]
        else:
            query = """
            DELETE FROM public.feedback
            WHERE (session_id = $1 OR conversation_id = $1)
              AND message_id = $2
            RETURNING feedback_id;
            """
            params = [session_id, message_id]

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            if rows and self.memory_service:
                for r in rows:
                    try:
                        await self.memory_service.remove_approved_memory(str(r["feedback_id"]))
                    except Exception as e:
                        logger.warning(f"Could not remove memory for feedback {r['feedback_id']}: {e}")
            return len(rows) > 0

    async def get_navigation_counts(self, company_id: Optional[str] = None) -> FeedbackCountsResponse:
        """Get fast counts of pending, approved, rejected, and total feedbacks."""
        await self.init_table()

        where_clauses = []
        params: List[Any] = []

        if company_id:
            params.append(str(company_id))
            where_clauses.append(f"company_id = ${len(params)}")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'pending') AS pending,
            COUNT(*) FILTER (WHERE status = 'approved') AS approved,
            COUNT(*) FILTER (WHERE status = 'rejected') AS rejected
        FROM public.feedback
        {where_sql};
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        return FeedbackCountsResponse(
            pending=int(row["pending"] or 0),
            approved=int(row["approved"] or 0),
            rejected=int(row["rejected"] or 0),
            total=int(row["total"] or 0),
        )

    async def get_dashboard_stats(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        company_id: Optional[str] = None,
        ship_type: Optional[str] = None,
        status: Optional[str] = None,
        feedback_type: Optional[str] = None,
        reviewer_id: Optional[str] = None,
    ) -> FeedbackDashboardResponse:
        """Compute all aggregated statistics for the feedback dashboard."""
        await self.init_table()

        # Build parameterized WHERE filters
        clauses = []
        params: List[Any] = []

        if from_date:
            params.append(from_date)
            clauses.append(f"created_at >= ${len(params)}")

        if to_date:
            params.append(to_date)
            clauses.append(f"created_at <= ${len(params)}")

        if company_id:
            params.append(str(company_id))
            clauses.append(f"company_id = ${len(params)}")

        if ship_type:
            params.append(ship_type)
            clauses.append(f"ship_type = ${len(params)}")

        if status:
            params.append(status.lower())
            clauses.append(f"status = ${len(params)}")

        if feedback_type:
            params.append(feedback_type.lower())
            clauses.append(f"feedback_type = ${len(params)}")

        if reviewer_id:
            params.append(reviewer_id)
            clauses.append(f"reviewed_by = ${len(params)}")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        async with self.pool.acquire() as conn:
            # 1. Summary KPIs
            summary_query = f"""
            SELECT
                COUNT(*) AS total_feedback,
                COUNT(*) FILTER (WHERE feedback_type = 'positive') AS positive_feedback,
                COUNT(*) FILTER (WHERE feedback_type = 'negative') AS negative_feedback,
                COUNT(*) FILTER (WHERE status = 'pending') AS pending_issues,
                COUNT(*) FILTER (WHERE status = 'approved') AS approved_issues,
                COUNT(*) FILTER (WHERE status = 'rejected') AS rejected_issues
            FROM public.feedback
            {where_sql};
            """
            sum_row = await conn.fetchrow(summary_query, *params)
            total = int(sum_row["total_feedback"] or 0)
            positive = int(sum_row["positive_feedback"] or 0)
            negative = int(sum_row["negative_feedback"] or 0)
            pending = int(sum_row["pending_issues"] or 0)
            approved = int(sum_row["approved_issues"] or 0)
            rejected = int(sum_row["rejected_issues"] or 0)

            sat_rate = round((positive / total) * 100, 1) if total > 0 else "N/A"
            pos_pct = round((positive / total) * 100, 1) if total > 0 else 0.0
            neg_pct = round((negative / total) * 100, 1) if total > 0 else 0.0

            summary = FeedbackSummary(
                total_feedback=total,
                positive_feedback=positive,
                negative_feedback=negative,
                pending_issues=pending,
                approved_issues=approved,
                rejected_issues=rejected,
                satisfaction_rate=sat_rate,
                positive_percentage=pos_pct,
                negative_percentage=neg_pct,
            )

            # 2. Daily Trend
            trend_query = f"""
            SELECT
                DATE(created_at) AS date_val,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE feedback_type = 'positive') AS positive,
                COUNT(*) FILTER (WHERE feedback_type = 'negative') AS negative
            FROM public.feedback
            {where_sql}
            GROUP BY DATE(created_at)
            ORDER BY date_val ASC;
            """
            trend_rows = await conn.fetch(trend_query, *params)
            trend_map = {
                r["date_val"].strftime("%Y-%m-%d"): {
                    "total": int(r["total"] or 0),
                    "positive": int(r["positive"] or 0),
                    "negative": int(r["negative"] or 0),
                }
                for r in trend_rows
                if r["date_val"]
            }

            # Build continuous date sequence for the trend
            start_d = (from_date.date() if from_date else (datetime.now(timezone.utc) - timedelta(days=29)).date())
            end_d = (to_date.date() if to_date else datetime.now(timezone.utc).date())
            if start_d > end_d:
                start_d, end_d = end_d, start_d

            trend: List[FeedbackTrendItem] = []
            curr = start_d
            while curr <= end_d:
                curr_str = curr.strftime("%Y-%m-%d")
                d_data = trend_map.get(curr_str, {"total": 0, "positive": 0, "negative": 0})
                trend.append(
                    FeedbackTrendItem(
                        date=curr_str,
                        total=d_data["total"],
                        positive=d_data["positive"],
                        negative=d_data["negative"],
                    )
                )
                curr += timedelta(days=1)

            # 3. Issue Categories (for negative feedback)
            cat_query = f"""
            SELECT
                COALESCE(category, 'Other') AS cat_name,
                COUNT(*) AS cat_count
            FROM public.feedback
            {where_sql} {'AND' if where_sql else 'WHERE'} feedback_type = 'negative'
            GROUP BY COALESCE(category, 'Other')
            ORDER BY cat_count DESC;
            """
            cat_rows = await conn.fetch(cat_query, *params)
            cat_dict = {r["cat_name"]: int(r["cat_count"] or 0) for r in cat_rows}

            # Ensure standard categories are present and ordered
            categories: List[FeedbackCategoryCount] = []
            for std_cat in STANDARD_CATEGORIES:
                c_count = cat_dict.get(std_cat, 0)
                c_pct = round((c_count / negative) * 100, 1) if negative > 0 else 0.0
                categories.append(
                    FeedbackCategoryCount(
                        category=std_cat,
                        count=c_count,
                        percentage=c_pct,
                    )
                )
            # Add any custom categories from db
            for cat_name, c_count in cat_dict.items():
                if cat_name not in STANDARD_CATEGORIES:
                    c_pct = round((c_count / negative) * 100, 1) if negative > 0 else 0.0
                    categories.append(
                        FeedbackCategoryCount(
                            category=cat_name,
                            count=c_count,
                            percentage=c_pct,
                        )
                    )

            # 4. Resolution Status
            status_query = f"""
            SELECT
                status,
                COUNT(*) AS status_count
            FROM public.feedback
            {where_sql}
            GROUP BY status;
            """
            status_rows = await conn.fetch(status_query, *params)
            status_map = {r["status"]: int(r["status_count"] or 0) for r in status_rows}

            resolution_status: List[FeedbackStatusCount] = [
                FeedbackStatusCount(
                    status="pending",
                    count=status_map.get("pending", 0),
                    percentage=round((status_map.get("pending", 0) / total) * 100, 1) if total > 0 else 0.0,
                ),
                FeedbackStatusCount(
                    status="approved",
                    count=status_map.get("approved", 0),
                    percentage=round((status_map.get("approved", 0) / total) * 100, 1) if total > 0 else 0.0,
                ),
                FeedbackStatusCount(
                    status="rejected",
                    count=status_map.get("rejected", 0),
                    percentage=round((status_map.get("rejected", 0) / total) * 100, 1) if total > 0 else 0.0,
                ),
            ]

            # 5. Reviewer / SME Resolution
            sme_query = f"""
            SELECT
                COALESCE(reviewed_by, 'unknown') AS rev_id,
                COALESCE(reviewed_by_name, 'Unknown Reviewer') AS rev_name,
                COUNT(*) FILTER (WHERE status = 'approved') AS approved_count,
                COUNT(*) FILTER (WHERE status = 'rejected') AS rejected_count,
                COUNT(*) AS total_resolved
            FROM public.feedback
            {where_sql} {'AND' if where_sql else 'WHERE'} status IN ('approved', 'rejected') AND (reviewed_by IS NOT NULL OR reviewed_by_name IS NOT NULL)
            GROUP BY COALESCE(reviewed_by, 'unknown'), COALESCE(reviewed_by_name, 'Unknown Reviewer')
            ORDER BY total_resolved DESC;
            """
            sme_rows = await conn.fetch(sme_query, *params)
            reviewer_resolution: List[FeedbackSmeResolution] = [
                FeedbackSmeResolution(
                    reviewer_id=r["rev_id"],
                    reviewer_name=r["rev_name"],
                    approved=int(r["approved_count"] or 0),
                    rejected=int(r["rejected_count"] or 0),
                    total_resolved=int(r["total_resolved"] or 0),
                )
                for r in sme_rows
            ]

            # 6. Pending Issue Aging
            # Age buckets: < 4 hours, 4–24 hours, 1–3 days, > 3 days
            aging_query = f"""
            SELECT
                COUNT(*) FILTER (WHERE NOW() - created_at < INTERVAL '4 hours') AS under_4h,
                COUNT(*) FILTER (WHERE NOW() - created_at >= INTERVAL '4 hours' AND NOW() - created_at < INTERVAL '24 hours') AS h4_to_24h,
                COUNT(*) FILTER (WHERE NOW() - created_at >= INTERVAL '24 hours' AND NOW() - created_at < INTERVAL '3 days') AS d1_to_3d,
                COUNT(*) FILTER (WHERE NOW() - created_at >= INTERVAL '3 days') AS over_3d
            FROM public.feedback
            {where_sql} {'AND' if where_sql else 'WHERE'} status = 'pending';
            """
            aging_row = await conn.fetchrow(aging_query, *params)
            aging: List[FeedbackAgingBucket] = [
                FeedbackAgingBucket(
                    age_bucket="< 4 hours",
                    count=int(aging_row["under_4h"] or 0),
                    is_oldest=False,
                ),
                FeedbackAgingBucket(
                    age_bucket="4–24 hours",
                    count=int(aging_row["h4_to_24h"] or 0),
                    is_oldest=False,
                ),
                FeedbackAgingBucket(
                    age_bucket="1–3 days",
                    count=int(aging_row["d1_to_3d"] or 0),
                    is_oldest=False,
                ),
                FeedbackAgingBucket(
                    age_bucket="> 3 days",
                    count=int(aging_row["over_3d"] or 0),
                    is_oldest=True,
                ),
            ]

            # 7. Recent Feedback Activity (latest 10)
            recent_query = f"""
            SELECT *
            FROM public.feedback
            {where_sql}
            ORDER BY created_at DESC
            LIMIT 10;
            """
            recent_rows = await conn.fetch(recent_query, *params)
            recent_feedback = [self._row_to_item(r) for r in recent_rows]

            # 8. Company-wise Analytics
            company_query = f"""
            SELECT
                company_id,
                COALESCE(company_name, company_id, 'Global') AS comp_name,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE feedback_type = 'positive') AS positive,
                COUNT(*) FILTER (WHERE feedback_type = 'negative') AS negative,
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE status = 'approved') AS approved
            FROM public.feedback
            {where_sql}
            GROUP BY company_id, COALESCE(company_name, company_id, 'Global')
            ORDER BY total DESC;
            """
            company_rows = await conn.fetch(company_query, *params)
            company_summary: List[FeedbackCompanySummary] = []
            for r in company_rows:
                c_tot = int(r["total"] or 0)
                c_pos = int(r["positive"] or 0)
                c_sat = round((c_pos / c_tot) * 100, 1) if c_tot > 0 else "N/A"
                company_summary.append(
                    FeedbackCompanySummary(
                        company_id=str(r["company_id"]) if r["company_id"] is not None else None,
                        company_name=r["comp_name"],
                        total=c_tot,
                        positive=c_pos,
                        negative=int(r["negative"] or 0),
                        pending=int(r["pending"] or 0),
                        approved=int(r["approved"] or 0),
                        satisfaction_rate=c_sat,
                    )
                )

            # 9. Ship Type Analytics
            ship_query = f"""
            SELECT
                ship_type,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE feedback_type = 'positive') AS positive,
                COUNT(*) FILTER (WHERE feedback_type = 'negative') AS negative,
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE status = 'approved') AS approved
            FROM public.feedback
            {where_sql} {'AND' if where_sql else 'WHERE'} ship_type IS NOT NULL AND ship_type != ''
            GROUP BY ship_type
            ORDER BY total DESC;
            """
            ship_rows = await conn.fetch(ship_query, *params)
            ship_type_summary: List[FeedbackShipTypeSummary] = []
            for r in ship_rows:
                s_tot = int(r["total"] or 0)
                s_pos = int(r["positive"] or 0)
                s_sat = round((s_pos / s_tot) * 100, 1) if s_tot > 0 else "N/A"
                ship_type_summary.append(
                    FeedbackShipTypeSummary(
                        ship_type=r["ship_type"],
                        total=s_tot,
                        positive=s_pos,
                        negative=int(r["negative"] or 0),
                        pending=int(r["pending"] or 0),
                        approved=int(r["approved"] or 0),
                        satisfaction_rate=s_sat,
                    )
                )

        return FeedbackDashboardResponse(
            summary=summary,
            trend=trend,
            categories=categories,
            resolution_status=resolution_status,
            reviewer_resolution=reviewer_resolution,
            aging=aging,
            recent_feedback=recent_feedback,
            company_summary=company_summary,
            ship_type_summary=ship_type_summary,
        )

    async def list_feedback(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        company_id: Optional[str] = None,
        ship_type: Optional[str] = None,
        feedback_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> PaginatedFeedbackResponse:
        """Fetch paginated feedback records with filtering."""
        await self.init_table()

        clauses = []
        params: List[Any] = []

        if status:
            params.append(status.lower())
            clauses.append(f"status = ${len(params)}")

        if category:
            params.append(category)
            clauses.append(f"category = ${len(params)}")

        if feedback_type:
            params.append(feedback_type.lower())
            clauses.append(f"feedback_type = ${len(params)}")

        if company_id:
            params.append(str(company_id))
            clauses.append(f"company_id = ${len(params)}")

        if ship_type:
            params.append(ship_type)
            clauses.append(f"ship_type = ${len(params)}")

        if from_date:
            params.append(from_date)
            clauses.append(f"created_at >= ${len(params)}")

        if to_date:
            params.append(to_date)
            clauses.append(f"created_at <= ${len(params)}")

        if search and search.strip():
            params.append(f"%{search.strip()}%")
            clauses.append(
                f"(question ILIKE ${len(params)} OR original_response ILIKE ${len(params)} OR comment ILIKE ${len(params)} OR user_name ILIKE ${len(params)})"
            )

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        count_query = f"SELECT COUNT(*) AS total FROM public.feedback {where_sql};"

        items_params = list(params)
        items_params.append(limit)
        limit_idx = len(items_params)
        items_params.append(offset)
        offset_idx = len(items_params)

        items_query = f"""
        SELECT *
        FROM public.feedback
        {where_sql}
        ORDER BY created_at DESC
        LIMIT ${limit_idx} OFFSET ${offset_idx};
        """

        async with self.pool.acquire() as conn:
            total_row = await conn.fetchrow(count_query, *params)
            total = int(total_row["total"] or 0)
            rows = await conn.fetch(items_query, *items_params)

        items = [self._row_to_item(r) for r in rows]
        return PaginatedFeedbackResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=items,
        )

    async def get_feedback_by_id(
        self,
        feedback_id: int,
        company_id: Optional[str] = None,
    ) -> Optional[FeedbackItem]:
        """Fetch a single feedback record by ID."""
        await self.init_table()

        clauses = ["feedback_id = $1"]
        params: List[Any] = [feedback_id]

        if company_id:
            params.append(str(company_id))
            clauses.append(f"company_id = ${len(params)}")

        query = f"SELECT * FROM public.feedback WHERE {' AND '.join(clauses)};"

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if not row:
            return None
        return self._row_to_item(row)

    async def review_feedback(
        self,
        feedback_id: int,
        payload: FeedbackReviewRequest,
        reviewer_id: Optional[str] = None,
        reviewer_name: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> Optional[FeedbackItem]:
        """Review, approve, reject, or edit a feedback item."""
        await self.init_table()

        # Verify item exists and check company authorization
        existing = await self.get_feedback_by_id(feedback_id, company_id=company_id)
        if not existing:
            return None

        status = payload.status.lower().strip()
        if status not in {"approved", "rejected", "pending"}:
            status = "approved"

        query = """
        UPDATE public.feedback
        SET
            status = $1,
            reviewed_by = COALESCE($2, reviewed_by),
            reviewed_by_name = COALESCE($3, reviewed_by_name),
            reviewer_notes = COALESCE($4, reviewer_notes),
            edited_response = COALESCE($5, edited_response),
            resolution_action = COALESCE($6, resolution_action),
            resolved_at = CASE WHEN $1 IN ('approved', 'rejected') THEN CURRENT_TIMESTAMP ELSE resolved_at END,
            updated_at = CURRENT_TIMESTAMP
        WHERE feedback_id = $7
        RETURNING *;
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                status,
                reviewer_id,
                reviewer_name,
                payload.reviewer_notes,
                payload.edited_response,
                payload.resolution_action,
                feedback_id,
            )

        if not row:
            return None
        logger.info(f"Feedback {feedback_id} reviewed by {reviewer_name or reviewer_id}: status={status}")

        # Trigger immediate response memory update for Dolphin AI retrieval
        try:
            from services.approved_memory_service import ApprovedMemoryService
            from services.embedding_service import EmbeddingService
            from services.openai_service import OpenAIService

            embedder = EmbeddingService(OpenAIService())
            memory_service = ApprovedMemoryService(self.pool, embedder=embedder)

            if status == "approved":
                preferred = row["edited_response"] or row["original_response"]
                if preferred and row["question"]:
                    await memory_service.sync_feedback_approval(
                        feedback_id=row["feedback_id"],
                        question=row["question"],
                        preferred_response=preferred,
                        original_response=row["original_response"],
                        company_id=str(row["company_id"]) if row["company_id"] is not None else None,
                        ship_type=row["ship_type"],
                        approved_by=reviewer_name or reviewer_id,
                        is_active=True,
                    )
            elif status in ("rejected", "pending"):
                await memory_service.sync_feedback_approval(
                    feedback_id=row["feedback_id"],
                    question=row["question"] or "",
                    preferred_response="",
                    is_active=False,
                )
        except Exception as mem_err:
            logger.warning(f"Immediate approved feedback memory sync error for id={feedback_id}: {mem_err}")

        return self._row_to_item(row)

