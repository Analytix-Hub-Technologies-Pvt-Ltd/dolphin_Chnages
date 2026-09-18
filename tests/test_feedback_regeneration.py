import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from loguru import logger

from main import app
from models.database import get_pool, init_feedback_tables


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_feedback_regeneration_flow():
    """
    Test the full flow:
    1. Submit irrelevant answer negative feedback.
    2. Call /feedback/{id}/regenerate with topic and manual reference.
    3. Verify generated response is structured and authoritative.
    4. Call /feedback/{id}/approve with the generated response.
    5. Verify database, memory, and DPO state.
    6. Clean up test record.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        pool = await get_pool()
        await init_feedback_tables(pool)

        # 1. Submit negative / irrelevant feedback
        submit_payload = {
            "question": "What are the required safety precautions for entering an enclosed space?",
            "original_response": "You can enter the space if you have a flashlight.",  # Completely wrong / irrelevant
            "feedback_type": "irrelevant_answer",
            "feedback_comment": "Completely wrong and unsafe advice. Lacks permit and atmospheric testing.",
            "user_id": "test_officer_99",
            "company_id": "Fleet_Management_Ltd",
            "ship_type": "Container",
        }

        submit_res = await client.post("/feedback", json=submit_payload)
        assert submit_res.status_code == 200, f"Submit failed: {submit_res.text}"
        feedback_item = submit_res.json()
        feedback_id = feedback_item["feedback_id"]
        assert feedback_item["status"] == "pending"
        logger.info(f"Created pending feedback: {feedback_id}")

        try:
            # 2. Call /feedback/{id}/regenerate with topic & reference
            regen_payload = {
                "topic": "SMS Section 4.2 Enclosed Space Entry Permit & Multi-Gas Testing Requirements",
                "reference_text": (
                    "Mandatory Requirements: 1. Continuous ventilation for 24h prior. "
                    "2. Gas test: O2 >= 20.9%, LEL < 1%, H2S < 5ppm, CO < 25ppm. "
                    "3. Enclosed space entry permit signed by Master/Chief Officer. "
                    "4. Standby person with SCBA and EEBD stationed at entrance."
                ),
                "reviewer_instructions": "Include standard responsibility table and emergency communication protocols.",
            }

            regen_res = await client.post(f"/feedback/{feedback_id}/regenerate", json=regen_payload)
            assert regen_res.status_code == 200, f"Regenerate failed: {regen_res.text}"
            regen_data = regen_res.json()

            assert regen_data["feedback_id"] == feedback_id
            assert regen_data["topic"] == regen_payload["topic"]
            assert regen_data["status"] == "success"
            assert regen_data["reference_text_used"] is True

            generated_response = regen_data["generated_response"]
            assert len(generated_response) > 100, "Generated response is too short"
            logger.info(f"Generated preferred response snippet: {generated_response[:200]}...")

            # 3. Approve feedback using generated response
            approve_payload = {
                "preferred_response": generated_response,
                "reviewer_id": "marine_superintendent_1",
                "admin_comment": "Verified and approved based on SMS Section 4.2",
            }

            approve_res = await client.post(f"/feedback/{feedback_id}/approve", json=approve_payload)
            assert approve_res.status_code == 200, f"Approve failed: {approve_res.text}"
            approved_item = approve_res.json()

            assert approved_item["status"] == "approved"
            assert approved_item["preferred_response"] == generated_response
            assert approved_item["reviewed_by"] == "marine_superintendent_1"

            # 4. Verify vector memory table has record
            async with pool.acquire() as conn:
                mem_row = await conn.fetchrow(
                    "SELECT * FROM public.approved_feedback_memory WHERE feedback_id = $1;",
                    feedback_id,
                )
                assert mem_row is not None, "Memory record was not inserted"
                assert mem_row["question"] == submit_payload["question"]

                dpo_row = await conn.fetchrow(
                    "SELECT * FROM public.dpo_dataset WHERE feedback_id = $1;",
                    feedback_id,
                )
                assert dpo_row is not None, "DPO dataset record was not inserted"
                assert dpo_row["chosen"] == generated_response

        finally:
            # 5. Clean up test records
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM public.dpo_dataset WHERE feedback_id = $1;", feedback_id)
                await conn.execute("DELETE FROM public.approved_feedback_memory WHERE feedback_id = $1;", feedback_id)
                await conn.execute("DELETE FROM public.feedback_records WHERE feedback_id = $1;", feedback_id)
            logger.info(f"Cleaned up test feedback item: {feedback_id}")
