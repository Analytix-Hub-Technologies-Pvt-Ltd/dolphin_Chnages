import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
from services.feedback_service import FeedbackService, STANDARD_CATEGORIES
from models.feedback_models import FeedbackCreateRequest, FeedbackReviewRequest


def test_feedback_service_create_positive():
    async def _run():
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        now = datetime.now(timezone.utc)
        mock_conn.fetchrow.return_value = {
            "feedback_id": 1,
            "user_id": "u1",
            "user_name": "Test User",
            "session_id": "s1",
            "conversation_id": "s1",
            "message_id": 1,
            "question": "What is SOLAS?",
            "original_response": "Safety of Life at Sea",
            "edited_response": None,
            "feedback_type": "positive",
            "rating": "positive",
            "category": None,
            "comment": None,
            "company_id": "c1",
            "company_name": "Test Co",
            "ship_type": "Tanker",
            "model_version": "dolphin-v1",
            "status": "approved",
            "reviewed_by": None,
            "reviewed_by_name": None,
            "reviewer_notes": None,
            "resolution_action": None,
            "created_at": now,
            "updated_at": now,
            "resolved_at": now,
        }

        service = FeedbackService(mock_pool)
        service.init_table = AsyncMock()

        item = await service.create_feedback(
            FeedbackCreateRequest(
                user_id="u1",
                user_name="Test User",
                session_id="s1",
                message_id=1,
                question="What is SOLAS?",
                original_response="Safety of Life at Sea",
                feedback_type="positive",
                company_id="c1",
                company_name="Test Co",
                ship_type="Tanker",
            )
        )

        assert item.feedback_id == 1
        assert item.feedback_type == "positive"
        assert item.status == "approved"

    asyncio.run(_run())


def test_feedback_service_create_negative():
    async def _run():
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        now = datetime.now(timezone.utc)
        mock_conn.fetchrow.return_value = {
            "feedback_id": 2,
            "user_id": "u2",
            "user_name": "Test User 2",
            "session_id": "s2",
            "conversation_id": "s2",
            "message_id": 2,
            "question": "What is COW?",
            "original_response": "Unknown",
            "edited_response": None,
            "feedback_type": "negative",
            "rating": "negative",
            "category": "Incorrect information",
            "comment": "Did not explain Crude Oil Washing",
            "company_id": "c2",
            "company_name": "Alpha Co",
            "ship_type": "Bulker",
            "model_version": "dolphin-v1",
            "status": "pending",
            "reviewed_by": None,
            "reviewed_by_name": None,
            "reviewer_notes": None,
            "resolution_action": None,
            "created_at": now,
            "updated_at": now,
            "resolved_at": None,
        }

        service = FeedbackService(mock_pool)
        service.init_table = AsyncMock()

        item = await service.create_feedback(
            FeedbackCreateRequest(
                user_id="u2",
                user_name="Test User 2",
                session_id="s2",
                message_id=2,
                question="What is COW?",
                original_response="Unknown",
                feedback_type="negative",
                category="Incorrect information",
                comment="Did not explain Crude Oil Washing",
                company_id="c2",
                company_name="Alpha Co",
                ship_type="Bulker",
            )
        )

        assert item.feedback_id == 2
        assert item.feedback_type == "negative"
        assert item.category == "Incorrect information"
        assert item.status == "pending"

    asyncio.run(_run())


def test_feedback_service_dashboard_aggregation():
    async def _run():
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        now = datetime.now(timezone.utc)

        # Mock fetchrow for summary KPIs
        mock_conn.fetchrow.side_effect = [
            # summary row
            {
                "total_feedback": 105,
                "positive_feedback": 82,
                "negative_feedback": 23,
                "pending_issues": 7,
                "approved_issues": 91,
                "rejected_issues": 14,
            },
            # aging row
            {
                "under_4h": 2,
                "h4_to_24h": 3,
                "d1_to_3d": 1,
                "over_3d": 1,
            },
        ]

        # Mock fetch calls for trend, categories, status, SME, company, ship_type
        mock_conn.fetch.side_effect = [
            # trend
            [
                {"date_val": (now - timedelta(days=1)).date(), "total": 10, "positive": 8, "negative": 2},
                {"date_val": now.date(), "total": 12, "positive": 9, "negative": 3},
            ],
            # categories
            [
                {"cat_name": "Incorrect information", "cat_count": 12},
                {"cat_name": "Didn't answer my question", "cat_count": 6},
                {"cat_name": "Irrelevant answer", "cat_count": 3},
                {"cat_name": "Incomplete answer", "cat_count": 1},
                {"cat_name": "Doesn't match company procedure", "cat_count": 1},
                {"cat_name": "Other", "cat_count": 0},
            ],
            # status
            [
                {"status": "pending", "status_count": 7},
                {"status": "approved", "status_count": 91},
                {"status": "rejected", "status_count": 14},
            ],
            # reviewer resolution
            [
                {"rev_id": "sme1", "rev_name": "SME Captain", "approved_count": 50, "rejected_count": 10, "total_resolved": 60},
            ],
            # recent feedback
            [],
            # company summary
            [
                {"company_id": "c1", "comp_name": "CMS Demo Company", "total": 75, "positive": 57, "negative": 18, "pending": 5, "approved": 70},
            ],
            # ship type summary
            [
                {"ship_type": "Tanker", "total": 40, "positive": 32, "negative": 8, "pending": 2, "approved": 38},
            ],
        ]

        service = FeedbackService(mock_pool)
        service.init_table = AsyncMock()

        res = await service.get_dashboard_stats()

        assert res.summary.total_feedback == 105
        assert res.summary.positive_feedback == 82
        assert res.summary.negative_feedback == 23
        assert res.summary.pending_issues == 7
        assert res.summary.approved_issues == 91
        assert res.summary.rejected_issues == 14
        # Satisfaction rate: 82 / 105 * 100 = 78.1%
        assert res.summary.satisfaction_rate == 78.1

        assert len(res.aging) == 4
        assert res.aging[3].is_oldest is True
        assert res.aging[3].count == 1

        assert len(res.categories) >= len(STANDARD_CATEGORIES)
        assert res.reviewer_resolution[0].reviewer_name == "SME Captain"
        assert res.reviewer_resolution[0].total_resolved == 60

    asyncio.run(_run())
