from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# REQUEST MODELS
# ---------------------------------------------------------------------------
class FeedbackCreateRequest(BaseModel):
    user_id: Optional[str] = "anonymous"
    user_name: Optional[str] = None
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message_id: Optional[int] = None
    question: Optional[str] = None
    original_response: Optional[str] = None
    feedback_type: str = Field(description="'positive' or 'negative'")
    rating: Optional[str] = None  # 'positive' or 'negative'
    category: Optional[str] = None  # 'Incorrect information', "Didn't answer my question", etc.
    comment: Optional[str] = None
    feedback_comment: Optional[str] = None
    source_metadata: Optional[Dict[str, Any]] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    ship_type: Optional[str] = None
    model_version: Optional[str] = "dolphin-v1"


class FeedbackReviewRequest(BaseModel):
    status: str = Field(description="'approved' or 'rejected'")
    reviewer_notes: Optional[str] = None
    edited_response: Optional[str] = None
    resolution_action: Optional[str] = None


class FeedbackApproveRequest(BaseModel):
    preferred_response: Optional[str] = None
    preferredResponse: Optional[str] = None
    question: Optional[str] = None
    reviewer_id: Optional[str] = "admin"
    reviewerId: Optional[str] = None
    reviewer_name: Optional[str] = None
    admin_comment: Optional[str] = None
    adminComment: Optional[str] = None
    company_id: Optional[str] = None
    companyId: Optional[str] = None
    ship_type: Optional[str] = None
    shipType: Optional[str] = None


class FeedbackRejectRequest(BaseModel):
    rejection_reason: Optional[str] = None
    rejectionReason: Optional[str] = None
    reviewer_id: Optional[str] = "admin"
    reviewerId: Optional[str] = None
    reviewer_name: Optional[str] = None
    admin_comment: Optional[str] = None
    adminComment: Optional[str] = None


class FeedbackRegenerateRequest(BaseModel):
    topic: Optional[str] = None
    reference_text: Optional[str] = None
    referenceText: Optional[str] = None
    reviewer_instructions: Optional[str] = None
    reviewerInstructions: Optional[str] = None
    company_id: Optional[str] = None
    ship_type: Optional[str] = None


# ---------------------------------------------------------------------------
# ITEM RESPONSE MODELS
# ---------------------------------------------------------------------------
class FeedbackItem(BaseModel):
    feedback_id: int
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message_id: Optional[int] = None
    question: Optional[str] = None
    original_response: Optional[str] = None
    edited_response: Optional[str] = None
    preferred_response: Optional[str] = None
    feedback_type: str
    category: Optional[str] = None
    comment: Optional[str] = None
    feedback_comment: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    ship_type: Optional[str] = None
    model_version: Optional[str] = None
    status: str  # 'pending', 'approved', 'rejected'
    reviewed_by: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    reviewer_notes: Optional[str] = None
    admin_comment: Optional[str] = None
    resolution_action: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None


class PaginatedFeedbackResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[FeedbackItem]


class FeedbackCountsResponse(BaseModel):
    pending: int
    approved: int
    rejected: int
    total: int


# ---------------------------------------------------------------------------
# DASHBOARD STATS MODELS
# ---------------------------------------------------------------------------
class FeedbackSummary(BaseModel):
    total_feedback: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0
    pending_issues: int = 0
    approved_issues: int = 0
    rejected_issues: int = 0
    satisfaction_rate: Any = "N/A"  # float or "N/A"
    positive_percentage: float = 0.0
    negative_percentage: float = 0.0


class FeedbackTrendItem(BaseModel):
    date: str
    total: int
    positive: int
    negative: int


class FeedbackCategoryCount(BaseModel):
    category: str
    count: int
    percentage: float


class FeedbackStatusCount(BaseModel):
    status: str
    count: int
    percentage: float


class FeedbackSmeResolution(BaseModel):
    reviewer_id: str
    reviewer_name: str
    approved: int
    rejected: int
    total_resolved: int


class FeedbackAgingBucket(BaseModel):
    age_bucket: str  # '< 4 hours', '4–24 hours', '1–3 days', '> 3 days'
    count: int
    is_oldest: bool = False


class FeedbackCompanySummary(BaseModel):
    company_id: Optional[str] = None
    company_name: str
    total: int
    positive: int
    negative: int
    pending: int
    approved: int
    satisfaction_rate: Any = "N/A"


class FeedbackShipTypeSummary(BaseModel):
    ship_type: str
    total: int
    positive: int
    negative: int
    pending: int
    approved: int
    satisfaction_rate: Any = "N/A"


class FeedbackDashboardResponse(BaseModel):
    summary: FeedbackSummary
    trend: List[FeedbackTrendItem]
    categories: List[FeedbackCategoryCount]
    resolution_status: List[FeedbackStatusCount]
    reviewer_resolution: List[FeedbackSmeResolution]
    aging: List[FeedbackAgingBucket]
    recent_feedback: List[FeedbackItem]
    company_summary: List[FeedbackCompanySummary]
    ship_type_summary: List[FeedbackShipTypeSummary]
