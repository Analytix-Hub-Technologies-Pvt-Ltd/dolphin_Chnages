import asyncio
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from services.status_service import DOLPHIN_STATUS_MESSAGES, get_status_event


def test_status_service_messages():
    """Verify predefined safe status events and message mappings."""
    expected_statuses = [
        "understanding",
        "searching",
        "company_search",
        "course_search",
        "analyzing",
        "preparing",
        "generating",
        "completed",
    ]
    for status in expected_statuses:
        assert status in DOLPHIN_STATUS_MESSAGES
        event = get_status_event(status)
        assert event["type"] == "status"
        assert event["status"] == status
        assert "message" in event
        # Verify no internal prompt leakage in predefined messages
        assert "prompt" not in event["message"].lower()
        assert "embedding" not in event["message"].lower()
        assert "sql" not in event["message"].lower()

    # Fallback status
    fallback = get_status_event("unknown_state")
    assert fallback["type"] == "status"
    assert fallback["message"] == "Dolphin is thinking..."


def test_chat_service_status_callbacks():
    """Verify ChatService.run_chat emits status callbacks at milestones."""
    async def _run():
        from services.chat_service import ChatService
        from models.node_response import NodeResponse

        mock_openai = MagicMock()
        mock_openai.chat = AsyncMock(return_value="Marine test answer")

        async def mock_stream(*args, **kwargs):
            yield '{"sections": [{"topic_code": "T1", "topic_name": "Test", "content": "Marine test answer"}], "suggestions": []}'

        mock_openai.stream_chat = mock_stream

        mock_embedder = MagicMock()
        mock_store = MagicMock()
        mock_session_service = MagicMock()
        mock_session_service.append_message = AsyncMock(return_value=[])
        mock_session_service.get_session_messages = AsyncMock(return_value=[])
        mock_session_service.update_session_messages = AsyncMock(return_value=[])

        service = ChatService(
            openai_service=mock_openai,
            embedder=mock_embedder,
            store=mock_store,
            session_service=mock_session_service,
        )

        service._retrieve_chunks = AsyncMock(return_value=([{"topic_code": "T1", "topic_name": "Test", "content": "Test content", "videos": [], "images": [], "pdfs": []}], []))
        service._run_company_retrieval = AsyncMock(return_value=[])
        service._load_checkpoint_state = MagicMock(return_value={})
        service._retrieve_approved_feedback_memory = AsyncMock(return_value=None)
        service._retrieve_meaningful_history = AsyncMock(return_value=[])
        service.get_session_user_profile = AsyncMock(return_value={"role": "Officer", "company_name": "Test Company"})
        service.analyzer.classify_for_router = AsyncMock(return_value={"node_type": "query", "category": "QUERY"})
        service.suggestion_service = MagicMock()
        service.suggestion_service.generate_from_response = MagicMock(return_value=[])
        service.append_message = AsyncMock(return_value=[{"role": "user", "content": "hello"}])
        service.rewrite_query = AsyncMock(return_value="What is snap back zone?")
        service.generate_understanding = AsyncMock(return_value="Understanding summary")
        service.check_query_scope = AsyncMock(return_value="IN-SCOPE")

        emitted_events = []

        async def on_token_collector(event: dict):
            emitted_events.append(event)

        with patch("services.chat_service.search_matching_videos_in_db", AsyncMock(return_value=[])), \
             patch("services.chat_service.search_matching_images_in_db", AsyncMock(return_value=[])), \
             patch("services.chat_service.ImageManager.process_and_cache_images", AsyncMock(return_value=[])):
            node_resp, updated_msgs, _, _, _ = await service.run_chat(
                user_id="test_user",
                session_id="test_session",
                db_messages=[],
                current_query="What is snap back zone?",
                on_token=on_token_collector,
            )

        status_events = [e for e in emitted_events if e.get("type") == "status"]
        statuses = [e.get("status") for e in status_events]

        # Verify key milestones were emitted in order
        assert "searching" in statuses
        assert "analyzing" in statuses
        assert "preparing" in statuses
        assert "generating" in statuses

        # Verify content tokens were also collected
        content_events = [e for e in emitted_events if e.get("type") == "content"]
        assert len(content_events) > 0

    asyncio.run(_run())


def test_query_node_emits_generating_status():
    """Verify query_node emits 'generating' status before LLM streaming."""
    from pipeline.query import query_node

    async def _run():
        mock_openai = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield '{"sections": [{"topic_code": "T1", "topic_name": "Test", "content": "Marine answer"}], "suggestions": []}'

        mock_openai.stream_chat = mock_stream
        mock_suggestion = MagicMock()

        state = {
            "current_query": "What is ECDIS?",
            "standalone_query": "What is ECDIS?",
            "retrieval_chunks": [
                {
                    "topic_code": "T1",
                    "topic_name": "Test",
                    "content": "ECDIS navigation information.",
                    "videos": [],
                    "images": [],
                    "pdfs": []
                }
            ],
            "router_decision": {"node_type": "query"},
            "user_profile": {"name": "Officer"}
        }

        emitted_events = []

        async def on_token_collector(event: dict):
            emitted_events.append(event)

        await query_node(state, mock_openai, mock_suggestion, on_token=on_token_collector)

        status_events = [e for e in emitted_events if e.get("type") == "status"]
        assert len(status_events) >= 1
        assert status_events[0]["status"] == "generating"
        assert status_events[0]["message"] == "Dolphin is generating your response..."

    asyncio.run(_run())


def test_company_query_node_emits_generating_status():
    """Verify company_query_node emits 'generating' status before LLM streaming."""
    from pipeline.company_query import company_query_node

    async def _run():
        mock_openai = MagicMock()

        async def mock_stream(*args, **kwargs):
            yield "### 🏢 1. Company SMS\nSafety manual content."

        mock_openai.stream_chat = mock_stream

        state = {
            "current_query": "What is safety drill procedure?",
            "standalone_query": "What is safety drill procedure?",
            "company_chunks": [
                {
                    "document_title": "SMS Manual.pdf",
                    "content": "Conduct drills monthly."
                }
            ],
            "user_profile": {"company_name": "Oceanic Corp", "company_id": "1"}
        }

        emitted_events = []

        async def on_token_collector(event: dict):
            emitted_events.append(event)

        await company_query_node(state, mock_openai, on_token=on_token_collector)

        status_events = [e for e in emitted_events if e.get("type") == "status"]
        assert len(status_events) >= 1
        assert status_events[0]["status"] == "generating"
        assert status_events[0]["message"] == "Dolphin is generating your response..."

    asyncio.run(_run())

