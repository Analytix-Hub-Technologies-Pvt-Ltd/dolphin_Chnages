import pytest
import asyncio
from services.followup_resolver import (
    is_followup_query,
    extract_topic_from_query,
    resolve_followup_retrieval_query,
    _extract_point_context_from_answer,
)
from services.chat_service import ChatService
from unittest.mock import AsyncMock, MagicMock


def test_extract_topic_from_query():
    assert extract_topic_from_query("Procedures for Enclosed Space Entry") == "Procedures for Enclosed Space Entry"
    assert extract_topic_from_query("Explain cargo loading sequence") == "Cargo Loading Sequence"
    assert extract_topic_from_query("What is boiler water treatment?") == "Boiler Water Treatment"
    assert extract_topic_from_query("Can you explain the COLREG Rule 15?") == "COLREG Rule 15"
    assert extract_topic_from_query("Now explain cargo loading sequence") == "Cargo Loading Sequence"
    assert extract_topic_from_query("Switch to boiler maintenance") == "Boiler Maintenance"


def test_is_followup_query():
    prev_q = ["Procedures for Enclosed Space Entry"]
    topic = "Procedures for Enclosed Space Entry"

    # Positive follow-up cases
    followup_cases = [
        "tell me more",
        "tell me in depth",
        "tell me indepth",
        "explain more",
        "elaborate",
        "give more details",
        "give me more details",
        "explain further",
        "continue",
        "go deeper",
        "more details",
        "details please",
        "deep dive",
        "in depth",
        "in-depth",
        "in detail",
        "what about this?",
        "explain that",
        "what are the requirements?",
        "what are the precautions?",
        "what are the safety precautions?",
        "give me the full procedure",
        "give me more information",
        "explain the above",
        "what are the specific checklists for this?",
        "who is responsible for this?",
        "what equipment is required?",
        "explain point 2",
        "tell me about step 3",
        "why so",
        "how does this work",
    ]

    for q in followup_cases:
        assert is_followup_query(q, prev_q, topic) is True, f"Failed to identify '{q}' as follow-up"

    # Negative cases (standalone new questions)
    standalone_cases = [
        "Procedures for Enclosed Space Entry",
        "Explain cargo loading sequence",
        "What is boiler water treatment?",
        "How does the oily water separator work?",
        "COLREG Rule 15 explanation",
        "Now explain cargo loading sequence",
        "Switch to bunker operations",
    ]

    for q in standalone_cases:
        assert is_followup_query(q, prev_q, topic) is False, f"Incorrectly marked '{q}' as follow-up"


def test_resolve_followup_retrieval_query():
    topic = "Procedures for Enclosed Space Entry"

    # 1. Depth expansion
    q_depth, is_depth = resolve_followup_retrieval_query("tell me indepth", topic)
    assert is_depth is True
    assert "Procedures for Enclosed Space Entry" in q_depth
    assert "detailed explanation" in q_depth or "comprehensive" in q_depth

    # 2. Checklists
    q_chk, is_depth_chk = resolve_followup_retrieval_query("what are the specific checklists for this?", topic)
    assert is_depth_chk is False
    assert "Procedures for Enclosed Space Entry" in q_chk
    assert "checklist" in q_chk.lower()

    # 3. Precautions
    q_prec, _ = resolve_followup_retrieval_query("what are the precautions?", topic)
    assert "Procedures for Enclosed Space Entry" in q_prec
    assert "precautions" in q_prec.lower() or "safety" in q_prec.lower()

    # 4. Requirements
    q_req, _ = resolve_followup_retrieval_query("what are the requirements?", topic)
    assert "Procedures for Enclosed Space Entry" in q_req
    assert "requirements" in q_req.lower() or "statutory" in q_req.lower()

    # 5. Full procedure
    q_proc, _ = resolve_followup_retrieval_query("give me the full procedure", topic)
    assert "Procedures for Enclosed Space Entry" in q_proc
    assert "procedure" in q_proc.lower() or "step-by-step" in q_proc.lower()


def test_point_context_extraction():
    last_answer = """
### Section 1
1. **Pre-entry Atmospheric Testing:** Oxygen content must be 20.9% and toxic gases zero.
2. **Ventilation and Continuous Monitoring:** Maintain forced ventilation throughout the operation.
3. **Emergency Rescue Arrangements:** Keep SCBA and resuscitation equipment ready at the entrance.
"""
    point_2 = _extract_point_context_from_answer("explain point 2", last_answer)
    assert "Ventilation and Continuous Monitoring" in point_2

    point_3 = _extract_point_context_from_answer("tell me more about the third point", last_answer)
    assert "Emergency Rescue Arrangements" in point_3


def test_chat_service_rewrite_query_fast_path():
    async def _run_test():
        # Setup mock OpenAI service
        mock_openai = MagicMock()
        mock_openai.chat = AsyncMock()

        mock_embedder = MagicMock()
        mock_store = MagicMock()

        chat_service = ChatService(
            openai_service=mock_openai,
            embedder=mock_embedder,
            store=mock_store,
        )

        prev_questions = ["Procedures for Enclosed Space Entry"]
        active_topic = "Procedures for Enclosed Space Entry"

        # Test 1: "tell me indepth" -> should resolve deterministically with 0 OpenAI calls
        rewritten = await chat_service.rewrite_query(
            current_query="tell me indepth",
            previous_questions=prev_questions,
            last_answer=None,
            conversation_topic=active_topic,
        )

        assert "Procedures for Enclosed Space Entry" in rewritten
        assert "detailed explanation" in rewritten
        # Verify OpenAI chat was NOT called (zero added LLM latency)
        mock_openai.chat.assert_not_called()

        # Test 2: "what are the specific checklists for this?"
        rewritten_chk = await chat_service.rewrite_query(
            current_query="what are the specific checklists for this?",
            previous_questions=prev_questions,
            last_answer=None,
            conversation_topic=active_topic,
        )

        assert "Procedures for Enclosed Space Entry" in rewritten_chk
        assert "checklist" in rewritten_chk.lower()
        mock_openai.chat.assert_not_called()

        # Test 3: Standalone clear question -> should fast-path return without LLM call
        rewritten_new = await chat_service.rewrite_query(
            current_query="Explain cargo loading sequence in detail",
            previous_questions=prev_questions,
            last_answer=None,
            conversation_topic=active_topic,
        )

        assert rewritten_new == "Explain cargo loading sequence in detail"
        mock_openai.chat.assert_not_called()

    asyncio.run(_run_test())
