from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class FeedbackSubmitRequest(BaseModel):
    question: str
    original_response: str
    feedback_type: str = Field(description="Category e.g. positive, irrelevant_answer, incorrect_information, does_not_match_procedure, incomplete_answer, did_not_answer_question, other")
    feedback_comment: Optional[str] = None
    user_id: Optional[str] = "anonymous"
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    company_id: Optional[str] = None
    ship_type: Optional[str] = None
    source_metadata: Optional[Dict[str, Any]] = None

    @field_validator("source_metadata", mode="before")
    @classmethod
    def parse_source_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v


class FeedbackApproveRequest(BaseModel):
    preferred_response: str = Field(min_length=1, description="Mandatory non-empty corrected/preferred response")
    question: Optional[str] = Field(None, description="Optional edited/refined question for feedback memory trigger")
    reviewer_id: Optional[str] = "admin"
    admin_comment: Optional[str] = None


class FeedbackRejectRequest(BaseModel):
    rejection_reason: str = Field(min_length=1, description="Mandatory non-empty reason for rejecting feedback")
    reviewer_id: Optional[str] = "admin"


class FeedbackRegenerateRequest(BaseModel):
    topic: str = Field(min_length=1, description="Topic, SOP name, section title, or reference keywords")
    reference_text: Optional[str] = Field(None, description="Optional manual excerpt, guidelines, or reference text")
    company_id: Optional[str] = None
    ship_type: Optional[str] = None
    reviewer_instructions: Optional[str] = None


class FeedbackRegenerateResponse(BaseModel):
    feedback_id: str
    topic: str
    generated_response: str
    status: str = "success"
    reference_text_used: bool = False


class FeedbackItemResponse(BaseModel):
    feedback_id: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    question: str
    original_response: str
    feedback_type: str
    feedback_comment: Optional[str] = None
    company_id: Optional[str] = None
    ship_type: Optional[str] = None
    source_metadata: Optional[Dict[str, Any]] = None
    status: str
    preferred_response: Optional[str] = None
    rejection_reason: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    admin_comment: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("source_metadata", mode="before")
    @classmethod
    def parse_item_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v


class FeedbackStatsResponse(BaseModel):
    pending_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    total_count: int = 0


class DpoDatasetItem(BaseModel):
    dpo_id: int
    feedback_id: str
    company_id: Optional[str] = None
    ship_type: Optional[str] = None
    prompt: str
    chosen: str
    rejected: str
    status: str
    dataset_version: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DpoJobCreateRequest(BaseModel):
    base_model: Optional[str] = "gpt-4o-mini"
    dataset_version: Optional[str] = "v1.0"
    company_id: Optional[str] = None


class DpoJobResponse(BaseModel):
    job_id: str
    company_id: Optional[str] = None
    dataset_version: str
    example_count: int
    base_model: str
    output_model: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("metadata", mode="before")
    @classmethod
    def parse_job_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v


# ============================================================
# Dashboard Analytics Models
# ============================================================

class FeedbackDashboardSummary(BaseModel):
    total_feedback: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0
    pending_issues: int = 0
    approved_issues: int = 0
    rejected_issues: int = 0
    satisfaction_rate: Optional[float] = None


class FeedbackTrendPoint(BaseModel):
    date: str
    total: int = 0
    positive: int = 0
    negative: int = 0


class FeedbackCategoryMetric(BaseModel):
    id: str
    label: str
    count: int = 0
    percentage: float = 0.0


class FeedbackResolutionMetric(BaseModel):
    status: str
    label: str
    count: int = 0
    percentage: float = 0.0


class ReviewerResolutionMetric(BaseModel):
    reviewer: str
    approved: int = 0
    rejected: int = 0
    total_resolved: int = 0


class PendingAgingMetric(BaseModel):
    bucket: str
    count: int = 0
    is_oldest: bool = False


class CompanyFeedbackMetric(BaseModel):
    company_id: str
    total: int = 0
    positive: int = 0
    negative: int = 0
    pending: int = 0
    approved: int = 0
    satisfaction_rate: Optional[float] = None


class ShipTypeFeedbackMetric(BaseModel):
    ship_type: str
    total: int = 0
    positive: int = 0
    negative: int = 0
    pending: int = 0
    approved: int = 0
    satisfaction_rate: Optional[float] = None


class FeedbackDashboardResponse(BaseModel):
    summary: FeedbackDashboardSummary
    trend: List[FeedbackTrendPoint] = []
    categories: List[FeedbackCategoryMetric] = []
    resolution_status: List[FeedbackResolutionMetric] = []
    reviewer_resolution: List[ReviewerResolutionMetric] = []
    aging: List[PendingAgingMetric] = []
    recent_feedback: List[FeedbackItemResponse] = []
    company_summary: List[CompanyFeedbackMetric] = []
    ship_type_summary: List[ShipTypeFeedbackMetric] = []
    filter_options: Optional[Dict[str, Any]] = None

