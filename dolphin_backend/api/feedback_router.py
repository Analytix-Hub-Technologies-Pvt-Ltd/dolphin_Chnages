from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from api.dependencies import get_db_pool, get_faiss_store, get_openai_service
from models.feedback_models import (
    FeedbackApproveRequest,
    FeedbackCountsResponse,
    FeedbackCreateRequest,
    FeedbackDashboardResponse,
    FeedbackItem,
    FeedbackRegenerateRequest,
    FeedbackRejectRequest,
    FeedbackReviewRequest,
    PaginatedFeedbackResponse,
)
from services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _parse_iso_date(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str or not dt_str.strip():
        return None
    cleaned = dt_str.strip()
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except Exception:
        logger.warning(f"Could not parse date string: {dt_str}")
        return None


@router.get("/dashboard", response_model=FeedbackDashboardResponse)
@router.get("/stats/dashboard", response_model=FeedbackDashboardResponse)
async def get_feedback_dashboard(
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD or ISO)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD or ISO)"),
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    ship_type: Optional[str] = Query(None, description="Filter by ship type"),
    status: Optional[str] = Query(None, description="Filter by status (pending, approved, rejected)"),
    feedback_type: Optional[str] = Query(None, description="Filter by feedback type (positive, negative)"),
    reviewer_id: Optional[str] = Query(None, description="Filter by reviewer ID"),
    pool: Pool = Depends(get_db_pool),
):
    """Retrieve aggregated metrics, trends, category breakdowns, aging, and recent activity for the feedback dashboard."""
    service = FeedbackService(pool)
    dt_from = _parse_iso_date(from_date)
    dt_to = _parse_iso_date(to_date)

    return await service.get_dashboard_stats(
        from_date=dt_from,
        to_date=dt_to,
        company_id=company_id,
        ship_type=ship_type,
        status=status,
        feedback_type=feedback_type,
        reviewer_id=reviewer_id,
    )


@router.get("/counts", response_model=FeedbackCountsResponse)
@router.get("/stats", response_model=FeedbackCountsResponse)
@router.get("/stats/counts", response_model=FeedbackCountsResponse)
async def get_feedback_counts(
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    pool: Pool = Depends(get_db_pool),
):
    """Fast endpoint to fetch pending, approved, and total counts for navigation badges."""
    service = FeedbackService(pool)
    return await service.get_navigation_counts(company_id=company_id)


@router.get("/pending", response_model=PaginatedFeedbackResponse)
async def get_pending_feedback(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search term in question/response/comment"),
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    ship_type: Optional[str] = Query(None, description="Filter by ship type"),
    from_date: Optional[str] = Query(None, description="Start date"),
    to_date: Optional[str] = Query(None, description="End date"),
    limit: int = Query(10, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    pool: Pool = Depends(get_db_pool),
):
    """List pending feedback items requiring review."""
    service = FeedbackService(pool)
    return await service.list_feedback(
        status="pending",
        category=category,
        search=search,
        company_id=company_id,
        ship_type=ship_type,
        from_date=_parse_iso_date(from_date),
        to_date=_parse_iso_date(to_date),
        limit=limit,
        offset=offset,
    )


@router.get("/approved", response_model=PaginatedFeedbackResponse)
async def get_approved_feedback(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search term in question/response/comment"),
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    ship_type: Optional[str] = Query(None, description="Filter by ship type"),
    from_date: Optional[str] = Query(None, description="Start date"),
    to_date: Optional[str] = Query(None, description="End date"),
    limit: int = Query(10, ge=1, le=100, description="Page limit"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    pool: Pool = Depends(get_db_pool),
):
    """List approved feedback items."""
    service = FeedbackService(pool)
    return await service.list_feedback(
        status="approved",
        category=category,
        search=search,
        company_id=company_id,
        ship_type=ship_type,
        from_date=_parse_iso_date(from_date),
        to_date=_parse_iso_date(to_date),
        limit=limit,
        offset=offset,
    )


@router.get("/topics/search")
async def search_topics_endpoint(
    query: str = Query("", description="Topic search query"),
    company_id: Optional[str] = Query(None, description="Company filter"),
    faiss_store=Depends(get_faiss_store),
):
    """Search available maritime course topics and titles."""
    results = []
    q_lower = query.lower().strip()
    
    meta_list = getattr(faiss_store, "id_to_metadata", None) or getattr(faiss_store, "metadata", []) or []
    if isinstance(meta_list, list):
        seen_topics = set()
        for chunk in meta_list:
            t_name = chunk.get("topic_name") or chunk.get("Title") or chunk.get("title") or ""
            t_code = chunk.get("topic_code") or ""
            if t_name and t_name not in seen_topics:
                if not q_lower or q_lower in t_name.lower() or q_lower in t_code.lower():
                    seen_topics.add(t_name)
                    results.append({
                        "topic_name": t_name,
                        "topic_code": t_code,
                        "source": chunk.get("source", "Course Content"),
                    })
                    if len(results) >= 20:
                        break

    return {"topics": results}


@router.get("/dpo/dataset")
async def get_dpo_dataset(
    company_id: Optional[str] = Query(None),
    dataset_version: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(500),
    pool: Pool = Depends(get_db_pool),
):
    """Fetch export of DPO preference pairs for fine-tuning."""
    from services.dpo_service import DPOService
    service = DPOService(pool)
    items = await service.export_dataset(
        company_id=company_id,
        dataset_version=dataset_version,
        status=status,
    )
    return {"total": len(items), "items": items[:limit]}


@router.post("/dpo/jobs")
async def create_dpo_job_endpoint(
    payload: Dict[str, Any],
    pool: Pool = Depends(get_db_pool),
):
    """Create offline DPO training job."""
    from services.dpo_service import DPOService
    service = DPOService(pool)
    return await service.create_training_job(
        company_id=payload.get("company_id"),
        dataset_version=payload.get("dataset_version", "v1.0"),
        base_model=payload.get("base_model", "gpt-4o-mini"),
    )


@router.get("/dpo/jobs")
async def list_dpo_jobs_endpoint(
    limit: int = Query(50),
    pool: Pool = Depends(get_db_pool),
):
    """List DPO training jobs."""
    from services.dpo_service import DPOService
    service = DPOService(pool)
    items = await service.list_training_jobs(limit=limit)
    return {"jobs": items}


@router.get("/{feedback_id}", response_model=FeedbackItem)
async def get_feedback_by_id(
    feedback_id: int,
    company_id: Optional[str] = Query(None, description="Verify company ownership if applicable"),
    pool: Pool = Depends(get_db_pool),
):
    """Get single feedback item by ID."""
    service = FeedbackService(pool)
    item = await service.get_feedback_by_id(feedback_id, company_id=company_id)
    if not item:
        raise HTTPException(status_code=404, detail="Feedback record not found")
    return item


@router.post("", response_model=FeedbackItem)
async def create_feedback(
    payload: FeedbackCreateRequest,
    pool: Pool = Depends(get_db_pool),
):
    """Submit feedback for a response (thumbs-up or thumbs-down)."""
    service = FeedbackService(pool)
    return await service.create_feedback(payload)


@router.post("/{feedback_id}/approve", response_model=FeedbackItem)
async def approve_feedback_post(
    feedback_id: int,
    payload: FeedbackApproveRequest,
    pool: Pool = Depends(get_db_pool),
):
    """Approve a feedback item with preferred response and optional edited question."""
    service = FeedbackService(pool)
    preferred = payload.preferred_response or payload.preferredResponse
    reviewer = payload.reviewer_id or payload.reviewerId or "admin"
    admin_comm = payload.admin_comment or payload.adminComment
    company = payload.company_id or payload.companyId

    # Update edited question if provided
    if payload.question and payload.question.strip():
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE public.feedback SET question = $1 WHERE feedback_id = $2",
                payload.question.strip(),
                feedback_id,
            )

    review_req = FeedbackReviewRequest(
        status="approved",
        reviewer_notes=admin_comm,
        edited_response=preferred,
        resolution_action="SME verified and approved",
    )
    updated = await service.review_feedback(
        feedback_id=feedback_id,
        payload=review_req,
        reviewer_id=reviewer,
        reviewer_name=payload.reviewer_name or reviewer,
        company_id=company,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Feedback record not found or unauthorized")

    # Add to DPO dataset if prompt and rejected response are available
    try:
        from services.dpo_service import DPOService
        dpo_svc = DPOService(pool)
        if updated.question and (updated.edited_response or updated.original_response):
            chosen_resp = updated.edited_response or updated.original_response
            rejected_resp = updated.original_response if updated.edited_response != updated.original_response else ""
            if rejected_resp:
                await dpo_svc.add_dpo_pair(
                    feedback_id=str(feedback_id),
                    prompt=updated.question,
                    chosen=chosen_resp,
                    rejected=rejected_resp,
                    company_id=updated.company_id,
                    ship_type=updated.ship_type,
                )
    except Exception as dpo_err:
        logger.warning(f"DPO pair creation skipped: {dpo_err}")

    return updated


@router.post("/{feedback_id}/reject", response_model=FeedbackItem)
async def reject_feedback_post(
    feedback_id: int,
    payload: FeedbackRejectRequest,
    pool: Pool = Depends(get_db_pool),
):
    """Reject a feedback item with mandatory rejection reason."""
    service = FeedbackService(pool)
    reason = payload.rejection_reason or payload.rejectionReason or "Rejected by SME"
    reviewer = payload.reviewer_id or payload.reviewerId or "admin"
    admin_comm = payload.admin_comment or payload.adminComment or reason

    review_req = FeedbackReviewRequest(
        status="rejected",
        reviewer_notes=admin_comm,
        resolution_action=reason,
    )
    updated = await service.review_feedback(
        feedback_id=feedback_id,
        payload=review_req,
        reviewer_id=reviewer,
        reviewer_name=payload.reviewer_name or reviewer,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Feedback record not found or unauthorized")
    return updated


@router.put("/{feedback_id}/approved", response_model=FeedbackItem)
async def update_approved_feedback_put(
    feedback_id: int,
    payload: FeedbackApproveRequest,
    pool: Pool = Depends(get_db_pool),
):
    """Update preferred response or question for an approved feedback item."""
    return await approve_feedback_post(feedback_id, payload, pool)


@router.delete("/{feedback_id}/approved")
async def delete_approved_feedback_delete(
    feedback_id: int,
    pool: Pool = Depends(get_db_pool),
):
    """Purge or deactivate an approved feedback item from vector memory."""
    service = FeedbackService(pool)
    review_req = FeedbackReviewRequest(
        status="rejected",
        reviewer_notes="Removed from approved memory by administrator",
        resolution_action="Deleted",
    )
    updated = await service.review_feedback(
        feedback_id=feedback_id,
        payload=review_req,
        reviewer_id="admin",
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Feedback record not found")
    return {"status": "deleted", "feedback_id": feedback_id}


@router.delete("/{feedback_id}")
async def delete_feedback_endpoint(
    feedback_id: int,
    pool: Pool = Depends(get_db_pool),
):
    """Delete a feedback record by ID (e.g. when un-voting or reverting feedback)."""
    service = FeedbackService(pool)
    deleted = await service.delete_feedback(feedback_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Feedback record not found")
    return {"status": "deleted", "feedback_id": feedback_id}


@router.delete("/session/{session_id}/message/{message_id}")
async def delete_feedback_by_message_endpoint(
    session_id: str,
    message_id: int,
    user_id: Optional[str] = Query(None),
    pool: Pool = Depends(get_db_pool),
):
    """Delete feedback for a specific session message (e.g. when un-voting)."""
    service = FeedbackService(pool)
    deleted = await service.delete_feedback_by_message(
        session_id=session_id,
        message_id=message_id,
        user_id=user_id,
    )
    return {"status": "deleted", "session_id": session_id, "message_id": message_id, "deleted": deleted}



@router.post("/{feedback_id}/regenerate")
async def regenerate_feedback_response(
    feedback_id: int,
    payload: FeedbackRegenerateRequest,
    pool: Pool = Depends(get_db_pool),
    openai_service=Depends(get_openai_service),
):
    """Regenerate a draft preferred response using OpenAI from topic or reference text."""
    service = FeedbackService(pool)
    item = await service.get_feedback_by_id(feedback_id)
    if not item:
        raise HTTPException(status_code=404, detail="Feedback record not found")

    question = item.question or "Maritime question"
    ref_topic = payload.topic or ""
    ref_text = payload.reference_text or payload.referenceText or ""
    instructions = payload.reviewer_instructions or payload.reviewerInstructions or ""

    system_prompt = (
        "You are an expert maritime educator and nautical SME. Generate a precise, compliant, "
        "and clear response to the user's question, incorporating the provided reference material "
        "and reviewer instructions. Format your answer using clean markdown headings, lists, and bold terms."
    )

    user_prompt = f"""Question:
{question}

Reference Topic / Context:
{ref_topic}
{ref_text}

SME Guidance / Instructions:
{instructions}

Please produce the corrected, high-standard answer for the training curriculum:"""

    try:
        response_text = await openai_service.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return {
            "generated_preferred_response": response_text.strip(),
            "feedback_id": feedback_id,
        }
    except Exception as e:
        logger.error(f"Failed to regenerate response for feedback_id={feedback_id}: {e}")
        raise HTTPException(status_code=500, detail=f"AI regeneration failed: {str(e)}")


@router.patch("/{feedback_id}/review", response_model=FeedbackItem)
async def review_feedback(
    feedback_id: int,
    payload: FeedbackReviewRequest,
    reviewer_id: Optional[str] = Query(None, description="ID of the reviewing SME/Admin"),
    reviewer_name: Optional[str] = Query(None, description="Name of the reviewing SME/Admin"),
    company_id: Optional[str] = Query(None, description="Company isolation check"),
    pool: Pool = Depends(get_db_pool),
):
    """Approve, reject, or edit response for a feedback item."""
    service = FeedbackService(pool)
    updated = await service.review_feedback(
        feedback_id=feedback_id,
        payload=payload,
        reviewer_id=reviewer_id,
        reviewer_name=reviewer_name,
        company_id=company_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Feedback record not found or unauthorized")
    return updated
