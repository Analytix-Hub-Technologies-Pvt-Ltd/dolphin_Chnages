from __future__ import annotations

from typing import Any, Dict, List, Optional
from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from api.dependencies import get_db_pool, get_embedding_service, get_openai_service
from models.feedback_models import (
    FeedbackApproveRequest,
    FeedbackDashboardResponse,
    FeedbackItemResponse,
    FeedbackRegenerateRequest,
    FeedbackRegenerateResponse,
    FeedbackRejectRequest,
    FeedbackStatsResponse,
    FeedbackSubmitRequest,
    DpoDatasetItem,
    DpoJobCreateRequest,
    DpoJobResponse,
)
from services.embedding_service import EmbeddingService
from services.feedback_memory_service import FeedbackMemoryService
from services.dpo_service import DPOService
from services.openai_service import OpenAIService
from services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


def get_feedback_service(
    pool: Pool = Depends(get_db_pool),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    openai_service: OpenAIService = Depends(get_openai_service),
) -> FeedbackService:
    memory_service = FeedbackMemoryService(pool, embedding_service)
    dpo_service = DPOService(pool)
    return FeedbackService(pool, memory_service, dpo_service, openai_service)


def get_dpo_service(pool: Pool = Depends(get_db_pool)) -> DPOService:
    return DPOService(pool)


# ============================================================
# 1. Feedback Submission, Badges & Dashboard Analytics
# ============================================================

@router.post("", response_model=FeedbackItemResponse)
async def submit_feedback(
    payload: FeedbackSubmitRequest,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    Submit user feedback for an AI response.
    - 👍 Positive feedback is saved directly.
    - 👎 Negative feedback enters the Pending admin review queue.
    """
    try:
        return await feedback_service.submit_feedback(payload)
    except Exception as e:
        logger.exception(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=FeedbackStatsResponse)
async def get_feedback_stats(
    company_id: Optional[str] = Query(None, description="Filter stats by company ID"),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    Get dynamic badge counts for Pending, Approved, and Rejected feedback.
    """
    try:
        return await feedback_service.get_feedback_stats(company_id=company_id)
    except Exception as e:
        logger.exception(f"Error fetching feedback stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard", response_model=FeedbackDashboardResponse)
@router.get("/stats/dashboard", response_model=FeedbackDashboardResponse)
async def get_feedback_dashboard(
    from_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    to_date: Optional[str] = Query(None, description="End date (ISO format)"),
    date_range: Optional[str] = Query("30d", description="Preset date range: today, 7d, 30d, 90d, custom"),
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    ship_type: Optional[str] = Query(None, description="Filter by ship type"),
    status: Optional[str] = Query(None, description="Filter by status: pending, approved, rejected, positive, all"),
    feedback_type: Optional[str] = Query(None, description="Filter by feedback category type"),
    reviewer_id: Optional[str] = Query(None, description="Filter by reviewing admin/SME"),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    Comprehensive aggregated analytics for the Dolphin AI Feedback Dashboard:
    - Top KPI cards (Total, Positive, Negative, Pending, Approved, Rejected, Satisfaction Rate)
    - Time-series feedback trend
    - Issue category breakdown
    - Resolution status breakdown
    - Issues resolved by SME/Admin
    - Pending issue aging buckets
    - Recent feedback activity stream
    - Company-wise & Ship-type analytics
    """
    try:
        return await feedback_service.get_dashboard_analytics(
            from_date=from_date,
            to_date=to_date,
            date_range=date_range,
            company_id=company_id,
            ship_type=ship_type,
            status=status,
            feedback_type=feedback_type,
            reviewer_id=reviewer_id,
        )
    except Exception as e:
        logger.exception(f"Error fetching feedback dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================
# 2. Lists (Pending & Approved)
# ============================================================

@router.get("/pending", response_model=List[FeedbackItemResponse])
async def list_pending_feedback(
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    search: str = Query("", description="Search term for query, comment, or ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    List feedback records pending administrator review.
    """
    try:
        return await feedback_service.list_pending_feedback(
            company_id=company_id,
            search=search,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.exception(f"Error listing pending feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approved", response_model=List[FeedbackItemResponse])
async def list_approved_feedback(
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    search: str = Query("", description="Search term for query, response, or reviewer"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    List approved feedback records active in semantic memory & DPO training.
    """
    try:
        return await feedback_service.list_approved_feedback(
            company_id=company_id,
            search=search,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.exception(f"Error listing approved feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 3. DPO Dataset & Training Jobs
# ============================================================

@router.get("/dpo/dataset", response_model=List[DpoDatasetItem])
async def get_dpo_dataset(
    company_id: Optional[str] = Query(None, description="Filter DPO examples by company ID"),
    status: Optional[str] = Query(None, description="Filter by status e.g. pending_training, trained"),
    limit: int = Query(500, ge=1, le=2000),
    dpo_service: DPOService = Depends(get_dpo_service),
):
    """
    Get compiled DPO training dataset pairs (prompt, chosen, rejected).
    """
    try:
        return await dpo_service.get_dpo_dataset(
            company_id=company_id,
            status=status,
            limit=limit,
        )
    except Exception as e:
        logger.exception(f"Error fetching DPO dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dpo/jobs", response_model=DpoJobResponse)
async def create_dpo_training_job(
    payload: DpoJobCreateRequest,
    dpo_service: DPOService = Depends(get_dpo_service),
):
    """
    Trigger automated background DPO training job.
    """
    try:
        return await dpo_service.create_and_run_training_job(
            base_model=payload.base_model or "gpt-4o-mini",
            dataset_version=payload.dataset_version or "v1.0",
            company_id=payload.company_id,
        )
    except Exception as e:
        logger.exception(f"Error creating DPO training job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dpo/jobs", response_model=List[DpoJobResponse])
async def list_dpo_training_jobs(
    limit: int = Query(50, ge=1, le=200),
    dpo_service: DPOService = Depends(get_dpo_service),
):
    """
    List all DPO training jobs and their progress/metrics.
    """
    try:
        return await dpo_service.list_jobs(limit=limit)
    except Exception as e:
        logger.exception(f"Error listing DPO jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dpo/jobs/{job_id}", response_model=DpoJobResponse)
async def get_dpo_job_status(
    job_id: str,
    dpo_service: DPOService = Depends(get_dpo_service),
):
    """
    Get status and results for a specific DPO training job.
    """
    job = await dpo_service.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="DPO training job not found")
    return job


# ============================================================
# 4. Detail Views & Admin Actions
# ============================================================

@router.get("/{feedback_id}", response_model=FeedbackItemResponse)
async def get_feedback_detail(
    feedback_id: str,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    Get full details for a single feedback item.
    """
    item = await feedback_service.get_feedback_by_id(feedback_id)
    if not item:
        raise HTTPException(status_code=404, detail="Feedback record not found")
    return item


@router.post("/{feedback_id}/approve", response_model=FeedbackItemResponse)
async def approve_feedback(
    feedback_id: str,
    payload: FeedbackApproveRequest,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    Agree & Approve feedback:
    - Stores admin preferred response
    - Creates 3072-dim vector memory for immediate RAG lookup
    - Adds to DPO training dataset
    - ⚡ Automatically launches background DPO training
    """
    return await feedback_service.approve_feedback(
        feedback_id=feedback_id,
        preferred_response=payload.preferred_response,
        question=payload.question,
        reviewer_id=payload.reviewer_id or "admin",
        admin_comment=payload.admin_comment,
    )


@router.put("/{feedback_id}/approved", response_model=FeedbackItemResponse)
async def update_approved_feedback(
    feedback_id: str,
    payload: FeedbackApproveRequest,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    Update existing approved feedback:
    - Updates preferred response & trigger question
    - Refreshes 3072-dim vector memory immediately
    """
    return await feedback_service.update_approved_feedback(
        feedback_id=feedback_id,
        preferred_response=payload.preferred_response,
        question=payload.question,
        reviewer_id=payload.reviewer_id or "admin",
        admin_comment=payload.admin_comment,
    )


@router.delete("/{feedback_id}/approved")
async def delete_approved_feedback(
    feedback_id: str,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    Delete approved feedback:
    - Purges vector memory
    - Removes from database
    """
    return await feedback_service.delete_approved_feedback(feedback_id=feedback_id)


@router.post("/{feedback_id}/reject", response_model=FeedbackItemResponse)
async def reject_feedback(
    feedback_id: str,
    payload: FeedbackRejectRequest,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    Reject feedback:
    - Requires mandatory rejection reason
    - Changes status to rejected
    - Excludes from feedback memory and DPO dataset
    """
    return await feedback_service.reject_feedback(
        feedback_id=feedback_id,
        rejection_reason=payload.rejection_reason,
        reviewer_id=payload.reviewer_id or "admin",
    )


@router.get("/topics/search")
async def search_reference_topics(
    query: str = Query("", description="Search term for course topics or company document titles"),
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    pool: Pool = Depends(get_db_pool),
):
    """
    Search reference topics from Course Content and Company Documents.
    Returns a list of suggested topics for the admin to select from.
    """
    clean_q = (query or "").strip()
    results = []
    try:
        async with pool.acquire() as conn:
            # 1. Search course_content
            if clean_q:
                course_rows = await conn.fetch(
                    """
                    SELECT DISTINCT topic_name, course_code, topic_code
                    FROM public.course_content
                    WHERE topic_name ILIKE $1 OR topic_code ILIKE $1 OR course_code ILIKE $1
                    ORDER BY topic_name ASC
                    LIMIT 8;
                    """,
                    f"%{clean_q}%",
                )
            else:
                course_rows = await conn.fetch(
                    """
                    SELECT DISTINCT topic_name, course_code, topic_code
                    FROM public.course_content
                    WHERE topic_name IS NOT NULL AND topic_name != ''
                    ORDER BY topic_name ASC
                    LIMIT 8;
                    """
                )

            for r in course_rows:
                results.append({
                    "title": r["topic_name"],
                    "subtitle": f"Course {r['course_code']} ({r['topic_code']})",
                    "source": "Course Curriculum",
                    "type": "course",
                })

            # 2. Search company_documents
            comp_id = str(company_id).strip() if company_id else None
            if clean_q:
                doc_rows = await conn.fetch(
                    """
                    SELECT DISTINCT document_name, topic, company_id
                    FROM public.company_documents
                    WHERE ($1::text IS NULL OR company_id = $1)
                      AND (document_name ILIKE $2 OR topic ILIKE $2)
                    ORDER BY document_name ASC
                    LIMIT 8;
                    """,
                    comp_id,
                    f"%{clean_q}%",
                )
            else:
                doc_rows = await conn.fetch(
                    """
                    SELECT DISTINCT document_name, topic, company_id
                    FROM public.company_documents
                    WHERE ($1::text IS NULL OR company_id = $1)
                    ORDER BY document_name ASC
                    LIMIT 8;
                    """,
                    comp_id,
                )

            for r in doc_rows:
                results.append({
                    "title": r["topic"] or r["document_name"],
                    "subtitle": f"Doc: {r['document_name']} ({r['company_id'] or 'Global'})",
                    "source": "Company SMS",
                    "type": "document",
                })
    except Exception as e:
        logger.warning(f"Error searching reference topics: {e}")

    return {"query": clean_q, "results": results}


@router.post("/{feedback_id}/regenerate", response_model=FeedbackRegenerateResponse)
async def regenerate_feedback_response(
    feedback_id: str,
    payload: FeedbackRegenerateRequest,
    feedback_service: FeedbackService = Depends(get_feedback_service),
):
    """
    AI-Assisted response generation based on Admin topic & manual reference:
    - Uses Admin-specified topic/SOP reference
    - Uses optional manual text/excerpt/guidelines
    - Synthesizes an authoritative, structured maritime HSQE/SMS preferred response
    - Returns response ready for review and approval
    """
    try:
        return await feedback_service.regenerate_preferred_response(
            feedback_id=feedback_id,
            topic=payload.topic,
            reference_text=payload.reference_text,
            reviewer_instructions=payload.reviewer_instructions,
            company_id=payload.company_id,
            ship_type=payload.ship_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error regenerating response for feedback '{feedback_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


