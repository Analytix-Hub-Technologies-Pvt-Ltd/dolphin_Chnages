import asyncio
import json
import os
import sys

# Ensure backend root is in sys.path and UTF-8 output
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from models.database import get_pool
from services.feedback_service import FeedbackService
from services.feedback_memory_service import FeedbackMemoryService
from services.dpo_service import DPOService
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService
from services.chat_service import ChatService
from models.feedback_models import FeedbackSubmitRequest


async def verify_feedback_flow():
    pool = await get_pool()
    openai_svc = OpenAIService()
    embedding_svc = EmbeddingService(openai_svc)
    dpo_svc = DPOService(pool)
    memory_svc = FeedbackMemoryService(pool, embedding_svc)
    fb_svc = FeedbackService(pool, memory_svc, dpo_svc)

    test_company = "comp_verify_test"
    test_question = "What is the specific valve procedure for emergency fire pump starting?"
    test_preferred_response = (
        "### 🏢 1. comp_verify_test Safety Management System (SMS)\n"
        "**SOP:** Emergency Fire Pump Operation\n\n"
        "**MANDATORY APPROVED INSTRUCTION:**\n"
        "1. Ensure suction valve **FP-V01** is locked 100% open.\n"
        "2. Verify safety bypass valve **SV-901** is tagged CLOSED.\n"
        "3. Prime pump using dedicated priming handle until casing pressure reaches **3.5 bar** before starting."
    )

    print("=" * 60)
    print("STEP 1: Submitting User Feedback")
    print("=" * 60)
    sub_req = FeedbackSubmitRequest(
        question=test_question,
        original_response="Turn the key and press the green start button on the panel.",
        feedback_type="incorrect_information",
        feedback_comment="Missing critical valve line-up FP-V01, SV-901, and priming step to 3.5 bar.",
        user_id="test_cadet_01",
        conversation_id="conv_test_fb_001",
        message_id="msg_test_001",
        company_id=test_company,
        ship_type="Oil Tanker",
        source_metadata={"category": "SMS_FIRE_PUMP"},
    )
    fb_record = await fb_svc.submit_feedback(sub_req)
    fb_id = fb_record["feedback_id"]
    print(f"✅ Feedback Submitted! ID: {fb_id}")
    print(f"   Status: {fb_record.get('status')}")
    print(f"   Feedback Type: {fb_record.get('feedback_type')}")
    print(f"   Company: {fb_record.get('company_id')}")

    print("\n" + "=" * 60)
    print("STEP 2: Admin / SME Approves the Feedback")
    print("=" * 60)
    approved_record = await fb_svc.approve_feedback(
        feedback_id=fb_id,
        preferred_response=test_preferred_response,
        reviewer_id="fleet_hsqe_superintendent",
        admin_comment="Approved according to Fleet SMS Chapter 9.4",
    )
    print(f"✅ Feedback Approved! Status: {approved_record.get('status')}")
    print(f"   Reviewed By: {approved_record.get('reviewed_by')}")
    print(f"   Preferred Response Saved into Vector Memory.")

    print("\n" + "=" * 60)
    print("STEP 3: Checking Semantic Vector Memory Retrieval")
    print("=" * 60)
    # Rephrase the question slightly to test semantic matching
    user_query = "how do i start the emergency fire pump and what valves to check?"
    print(f"User asks subsequent rephrased query: '{user_query}'")

    memory_hit = await memory_svc.find_relevant_feedback_preference(
        query=user_query,
        company_id=test_company,
        ship_type="Oil Tanker",
        threshold=0.60,
    )

    if memory_hit:
        print(f"🎯 Memory Match Found!")
        print(f"   - Feedback ID: {memory_hit.get('feedback_id')}")
        print(f"   - Matched Question: {memory_hit.get('question')}")
        print(f"   - Cosine Similarity: {memory_hit.get('similarity')}")
        print(f"   - Effective Similarity (with company boost): {memory_hit.get('effective_similarity')}")
    else:
        print("❌ Memory not found! Threshold or embedding mismatch.")
        return

    print("\n" + "=" * 60)
    print("STEP 4: Executing Chat Pipeline (Calling LLM with Prompt Enrichment)")
    print("=" * 60)
    from api.dependencies import get_faiss_store, get_company_store
    faiss_store = get_faiss_store()
    company_store = get_company_store()
    chat_svc = ChatService(
        openai_service=openai_svc,
        embedder=embedding_svc,
        store=faiss_store,
        company_store=company_store,
    )
    user_profile = {
        "company_id": test_company,
        "company_name": test_company,
        "ship_name": "MT Test Star",
        "ship_type": "Oil Tanker",
        "role": "Third Engineer",
        "name": "Alex Officer",
    }

    node_resp, chunks, cat, stand_q, extra = await chat_svc.run_chat(
        user_id="test_cadet_01",
        session_id=f"sess_fb_verify_{fb_id}",
        db_messages=[],
        current_query=user_query,
        user_details=user_profile,
    )

    content = node_resp.content if hasattr(node_resp, "content") else node_resp.get("content", "")
    print("\n" + "=" * 60)
    print("STEP 5: AI Generated Response Output")
    print("=" * 60)
    print(content)

    print("\n" + "=" * 60)
    print("STEP 6: Point-by-Point Verification of Approved Points in Response")
    print("=" * 60)
    points = {
        "Suction valve FP-V01": "FP-V01" in content,
        "Safety bypass valve SV-901": "SV-901" in content,
        "Casing pressure 3.5 bar": ("3.5 bar" in content or "3.5" in content),
    }

    all_passed = True
    for pt, passed in points.items():
        status_icon = "✅ INCLUDED" if passed else "❌ MISSING"
        print(f"  {status_icon} -> {pt}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("🎉 ALL APPROVED FEEDBACK POINTS WERE SUCCESSFULLY ADDED AND INJECTED!")
    else:
        print("⚠️ Some approved points were missing.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(verify_feedback_flow())
