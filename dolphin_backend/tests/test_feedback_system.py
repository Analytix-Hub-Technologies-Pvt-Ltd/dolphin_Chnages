import asyncio
import json
import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from models.database import get_pool, init_feedback_tables
from services.feedback_memory_service import cosine_similarity, FeedbackMemoryService
from services.dpo_service import DPOService
from services.feedback_service import FeedbackService


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_cosine_similarity_math():
    """Verify vector math properties."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(v1, v2) - 1.0) < 1e-5

    v_orth = [0.0, 1.0, 0.0]
    assert abs(cosine_similarity(v1, v_orth) - 0.0) < 1e-5

    v_empty = []
    assert cosine_similarity(v1, v_empty) == 0.0


@pytest.mark.anyio
async def test_positive_feedback_submission():
    """Test submitting positive feedback."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        pool = await get_pool()
        await init_feedback_tables(pool)

        payload = {
            "question": "What is the flash point limit for low flash point fuels?",
            "original_response": "Low flash point fuels have a flash point below 60°C as regulated by the IGF Code.",
            "feedback_type": "positive",
            "feedback_comment": "User rated helpful 👍",
            "user_id": "test_cadet_1",
            "conversation_id": "conv_test_pos_001",
            "message_id": "msg_001",
            "company_id": "comp_alpha",
            "ship_type": "Oil Tanker",
            "source_metadata": {"sources": ["SMS Section 4", "IGF Code Ch 5"]},
        }

        res = await client.post("/feedback", json=payload)
        assert res.status_code == 200, f"Submit positive feedback failed: {res.text}"
        data = res.json()
        assert data["feedback_id"].startswith("fb_")
        assert data["status"] == "positive"
        assert data["feedback_type"] == "positive"
        assert data["company_id"] == "comp_alpha"


@pytest.mark.anyio
async def test_negative_feedback_submission():
    """Test submitting negative feedback which should become 'pending'."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        pool = await get_pool()
        await init_feedback_tables(pool)

        payload = {
            "question": "What are the enclosed space entry requirements?",
            "original_response": "Open the door and enter with a flashlight.",
            "feedback_type": "incorrect_information",
            "feedback_comment": "Incorrect oxygen percentage and missing permit procedure.",
            "user_id": "test_officer_2",
            "conversation_id": "conv_test_neg_002",
            "message_id": "msg_002",
            "company_id": "comp_alpha",
            "ship_type": "Chemical Tanker",
            "source_metadata": {"category": "SMS_ENCLOSED_SPACE"},
        }

        res = await client.post("/feedback", json=payload)
        assert res.status_code == 200, f"Submit negative feedback failed: {res.text}"
        data = res.json()
        assert data["feedback_id"].startswith("fb_")
        assert data["status"] == "pending"
        assert data["feedback_type"] == "incorrect_information"
        assert data["feedback_comment"] == "Incorrect oxygen percentage and missing permit procedure."

        # Verify stats reflect the new pending item
        stats_res = await client.get("/feedback/stats?company_id=comp_alpha")
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert stats["pending_count"] >= 1


@pytest.mark.anyio
async def test_pending_feedback_listing_and_filtering():
    """Test fetching pending feedback list and search filter."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        pool = await get_pool()
        await init_feedback_tables(pool)

        res = await client.get("/feedback/pending?company_id=comp_alpha&limit=50")
        assert res.status_code == 200
        items = res.json()
        assert isinstance(items, list)
        assert len(items) >= 1

        # Search by keyword
        search_res = await client.get("/feedback/pending?company_id=comp_alpha&search=enclosed")
        assert search_res.status_code == 200
        search_items = search_res.json()
        assert any("enclosed" in it["question"].lower() for it in search_items)


@pytest.mark.anyio
async def test_feedback_approval_workflow_and_auto_dpo():
    """
    Test approval workflow:
    - Empty preferred response is rejected with 400.
    - Valid preferred response approves feedback, creates memory and DPO record, and automatically launches training.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        pool = await get_pool()
        await init_feedback_tables(pool)

        # 1. Create a pending item
        sub_res = await client.post(
            "/feedback",
            json={
                "question": "What is the minimum oxygen level before entering an enclosed space?",
                "original_response": "18% is acceptable.",
                "feedback_type": "incorrect_information",
                "feedback_comment": "Oxygen level must be at least 20.9% by volume.",
                "user_id": "test_user_3",
                "company_id": "comp_alpha",
                "ship_type": "Chemical Tanker",
            },
        )
        assert sub_res.status_code == 200
        fb_id = sub_res.json()["feedback_id"]

        # 2. Try approving with empty string -> should fail with 422/400
        fail_res = await client.post(f"/feedback/{fb_id}/approve", json={"preferred_response": "   "})
        assert fail_res.status_code in [400, 422]

        # 3. Approve with valid preferred response
        preferred_text = (
            "### 🏢 1. comp_alpha's Safety Management System (SMS / QMS)\n"
            "**Document Title:** Shipboard SMS Manual - Safety\n"
            "**SOP Name:** Enclosed Space Entry\n"
            "**Section:** Atmosphere Testing\n\n"
            "The steady oxygen reading must be exactly **20.9% by volume** before any entry is permitted under Form SS 004."
        )
        app_res = await client.post(
            f"/feedback/{fb_id}/approve",
            json={
                "preferred_response": preferred_text,
                "reviewer_id": "admin_chief_officer",
                "admin_comment": "Corrected according to SMS Chapter 7.2",
            },
        )
        assert app_res.status_code == 200, f"Approve failed: {app_res.text}"
        approved_data = app_res.json()
        assert approved_data["status"] == "approved"
        assert approved_data["reviewed_by"] == "admin_chief_officer"
        assert approved_data["preferred_response"] == preferred_text

        # 4. Verify detail endpoint reflects approval
        detail_res = await client.get(f"/feedback/{fb_id}")
        assert detail_res.status_code == 200
        assert detail_res.json()["status"] == "approved"

        # 5. Verify DPO dataset item exists
        dpo_res = await client.get("/feedback/dpo/dataset?company_id=comp_alpha")
        assert dpo_res.status_code == 200
        dpo_items = dpo_res.json()
        matching_dpo = next((d for d in dpo_items if d["feedback_id"] == fb_id), None)
        assert matching_dpo is not None
        assert matching_dpo["chosen"] == preferred_text
        assert matching_dpo["rejected"] == "18% is acceptable."

        # 6. Verify automated background DPO training job was triggered
        jobs_res = await client.get("/feedback/dpo/jobs")
        assert jobs_res.status_code == 200
        jobs = jobs_res.json()
        assert len(jobs) >= 1
        latest_job = jobs[0]
        assert latest_job["status"] in ["queued", "running", "completed"]


@pytest.mark.anyio
async def test_feedback_rejection_workflow():
    """
    Test rejection workflow:
    - Empty rejection reason is rejected with 400.
    - Valid rejection sets status to 'rejected' with mandatory reason.
    - Confirms rejection does not enter approved memory or DPO dataset.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        pool = await get_pool()
        await init_feedback_tables(pool)

        # 1. Create a pending item
        sub_res = await client.post(
            "/feedback",
            json={
                "question": "How to start emergency fire pump?",
                "original_response": "Turn the key and press start.",
                "feedback_type": "incomplete_answer",
                "feedback_comment": "Needs more details.",
                "user_id": "test_user_4",
                "company_id": "comp_alpha",
            },
        )
        assert sub_res.status_code == 200
        fb_id = sub_res.json()["feedback_id"]

        # 2. Try rejecting without reason -> should fail with 422/400
        fail_res = await client.post(f"/feedback/{fb_id}/reject", json={"rejection_reason": ""})
        assert fail_res.status_code in [400, 422]

        # 3. Reject with valid reason
        rej_res = await client.post(
            f"/feedback/{fb_id}/reject",
            json={
                "rejection_reason": "Original answer was already procedurally sufficient for quick overview.",
                "reviewer_id": "admin_safety_manager",
            },
        )
        assert rej_res.status_code == 200
        rejected_data = rej_res.json()
        assert rejected_data["status"] == "rejected"
        assert rejected_data["rejection_reason"] == "Original answer was already procedurally sufficient for quick overview."

        # 4. Verify item does NOT appear in Approved list
        approved_res = await client.get("/feedback/approved?company_id=comp_alpha")
        assert approved_res.status_code == 200
        approved_items = approved_res.json()
        assert not any(item["feedback_id"] == fb_id for item in approved_items)

        # 5. Verify item does NOT appear in Pending list
        pending_res = await client.get("/feedback/pending?company_id=comp_alpha")
        assert pending_res.status_code == 200
        pending_items = pending_res.json()
        assert not any(item["feedback_id"] == fb_id for item in pending_items)


@pytest.mark.anyio
async def test_feedback_memory_company_isolation():
    """
    Test strict company isolation for Approved Feedback Memory:
    Company A approved feedback memory MUST NEVER leak to Company B.
    """
    pool = await get_pool()
    from api.dependencies import get_embedding_service, get_openai_service
    embedder = get_embedding_service(get_openai_service())
    memory_svc = FeedbackMemoryService(pool, embedder)

    # Search for company A
    res_a = await memory_svc.find_relevant_feedback_preference(
        query="What is the minimum oxygen percentage for enclosed space entry?",
        company_id="comp_alpha",
        ship_type="Chemical Tanker",
        threshold=0.60,
    )
    if res_a:
        assert res_a["company_id"] == "comp_alpha"

    # Search the EXACT same query for company B -> MUST return None (strict company isolation)
    res_b = await memory_svc.find_relevant_feedback_preference(
        query="What is the minimum oxygen percentage for enclosed space entry?",
        company_id="comp_beta_other",
        ship_type="Chemical Tanker",
        threshold=0.60,
    )
    assert res_b is None, "Security Violation: Company A feedback leaked to Company B!"


@pytest.mark.anyio
async def test_feedback_dashboard_aggregation():
    """
    Test Feedback Dashboard analytics endpoint:
    - Verifies summary KPI counts and satisfaction rate calculation.
    - Verifies trend, issue categories, resolution status, reviewer resolution, aging, and recent activity.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        pool = await get_pool()
        await init_feedback_tables(pool)

        # 1. Fetch dashboard
        res = await client.get("/feedback/dashboard?date_range=30d")
        assert res.status_code == 200, f"Dashboard failed: {res.text}"
        data = res.json()

        # Check summary structure
        summary = data["summary"]
        assert "total_feedback" in summary
        assert "positive_feedback" in summary
        assert "negative_feedback" in summary
        assert "pending_issues" in summary
        assert "approved_issues" in summary
        assert "rejected_issues" in summary
        assert "satisfaction_rate" in summary
        assert summary["total_feedback"] == summary["positive_feedback"] + summary["negative_feedback"]

        # Check trend
        assert isinstance(data["trend"], list)

        # Check categories
        assert isinstance(data["categories"], list)
        assert len(data["categories"]) >= 5
        cat_labels = [c["label"] for c in data["categories"]]
        assert "Incorrect information" in cat_labels

        # Check resolution status
        assert isinstance(data["resolution_status"], list)
        res_statuses = [r["status"] for r in data["resolution_status"]]
        assert "pending" in res_statuses
        assert "approved" in res_statuses
        assert "rejected" in res_statuses

        # Check aging
        assert isinstance(data["aging"], list)
        assert len(data["aging"]) == 4
        aging_buckets = [a["bucket"] for a in data["aging"]]
        assert "< 4 hours" in aging_buckets
        assert "> 3 days" in aging_buckets

        # Check recent feedback
        assert isinstance(data["recent_feedback"], list)


@pytest.mark.anyio
async def test_feedback_dashboard_filters():
    """
    Test Feedback Dashboard with company_id, feedback_type, and status filters.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        pool = await get_pool()
        await init_feedback_tables(pool)

        # Filter by company
        res_comp = await client.get("/feedback/dashboard?company_id=comp_alpha")
        assert res_comp.status_code == 200
        comp_data = res_comp.json()
        assert comp_data["summary"]["total_feedback"] >= 0

        # Filter by status = pending
        res_status = await client.get("/feedback/dashboard?status=pending")
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert status_data["summary"]["pending_issues"] >= 0

        # Filter by date_range = 7d
        res_7d = await client.get("/feedback/dashboard?date_range=7d")
        assert res_7d.status_code == 200


@pytest.mark.anyio
async def test_feedback_dashboard_zero_division_safety():
    """
    Test Feedback Dashboard zero division safety when no feedback matches:
    - satisfaction_rate must be None (not NaN or error).
    - All counts must be 0 without throwing errors.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        pool = await get_pool()
        await init_feedback_tables(pool)

        res = await client.get("/feedback/dashboard?company_id=non_existent_company_999999")
        assert res.status_code == 200
        data = res.json()
        summary = data["summary"]
        assert summary["total_feedback"] == 0
        assert summary["positive_feedback"] == 0
        assert summary["negative_feedback"] == 0
        assert summary["satisfaction_rate"] is None


@pytest.mark.anyio
async def test_distinctive_terms_for_comparison_queries():
    """
    Verify that comparative/framing terms (e.g. 'difference', 'between', 'compare')
    are excluded from distinctive terms so general questions (e.g. EEDI vs CII)
    do not falsely match unrelated company documents.
    """
    from retrieval.normalization import extract_distinctive_terms

    terms_eedi_cii = extract_distinctive_terms("difference between EEDI and CII")
    assert "difference" not in terms_eedi_cii
    assert "between" not in terms_eedi_cii
    assert "eedi" in terms_eedi_cii
    assert "cii" in terms_eedi_cii

    terms_compare = extract_distinctive_terms("compare SOLAS and MARPOL requirements")
    assert "compare" not in terms_compare
    assert "solas" in terms_compare
    assert "marpol" in terms_compare


