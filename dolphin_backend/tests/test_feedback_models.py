import pytest
from datetime import datetime, timezone
from models.feedback_models import (
    FeedbackCreateRequest,
    FeedbackReviewRequest,
    FeedbackSummary,
    FeedbackTrendItem,
    FeedbackCategoryCount,
    FeedbackStatusCount,
    FeedbackAgingBucket,
    FeedbackCompanySummary,
    FeedbackDashboardResponse,
)


def test_feedback_create_request():
    req = FeedbackCreateRequest(
        user_id="user-123",
        question="What is SOLAS?",
        original_response="SOLAS is the International Convention for the Safety of Life at Sea.",
        feedback_type="negative",
        category="Incorrect information",
        comment="Incomplete citation",
        company_id="comp_1",
    )
    assert req.feedback_type == "negative"
    assert req.category == "Incorrect information"


def test_feedback_summary_satisfaction_rate_calculation():
    # Normal case
    total = 100
    pos = 85
    neg = 15
    sat = round((pos / total) * 100, 1)
    summary = FeedbackSummary(
        total_feedback=total,
        positive_feedback=pos,
        negative_feedback=neg,
        pending_issues=5,
        approved_issues=85,
        rejected_issues=10,
        satisfaction_rate=sat,
        positive_percentage=85.0,
        negative_percentage=15.0,
    )
    assert summary.satisfaction_rate == 85.0
    assert summary.total_feedback == 100

    # Zero feedback safe case
    zero_summary = FeedbackSummary(
        total_feedback=0,
        positive_feedback=0,
        negative_feedback=0,
        pending_issues=0,
        approved_issues=0,
        rejected_issues=0,
        satisfaction_rate="N/A",
        positive_percentage=0.0,
        negative_percentage=0.0,
    )
    assert zero_summary.satisfaction_rate == "N/A"
    assert zero_summary.total_feedback == 0


def test_feedback_dashboard_response_structure():
    dashboard = FeedbackDashboardResponse(
        summary=FeedbackSummary(
            total_feedback=10,
            positive_feedback=8,
            negative_feedback=2,
            pending_issues=2,
            approved_issues=8,
            rejected_issues=0,
            satisfaction_rate=80.0,
        ),
        trend=[
            FeedbackTrendItem(date="2026-09-01", total=10, positive=8, negative=2)
        ],
        categories=[
            FeedbackCategoryCount(category="Incorrect information", count=2, percentage=100.0)
        ],
        resolution_status=[
            FeedbackStatusCount(status="pending", count=2, percentage=20.0),
            FeedbackStatusCount(status="approved", count=8, percentage=80.0),
            FeedbackStatusCount(status="rejected", count=0, percentage=0.0),
        ],
        reviewer_resolution=[],
        aging=[
            FeedbackAgingBucket(age_bucket="< 4 hours", count=1, is_oldest=False),
            FeedbackAgingBucket(age_bucket="> 3 days", count=1, is_oldest=True),
        ],
        recent_feedback=[],
        company_summary=[],
        ship_type_summary=[],
    )
    assert dashboard.summary.satisfaction_rate == 80.0
    assert len(dashboard.trend) == 1
    assert dashboard.aging[1].is_oldest is True
