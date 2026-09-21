import asyncio
import pytest
from unittest.mock import MagicMock
from pipeline.stream_utils import JsonStreamContentExtractor
from pipeline.query import query_node
from pipeline.company_query import company_query_node


def test_stream_extractor_json_single_section():
    extractor = JsonStreamContentExtractor()
    sample_json = '''{
  "sections": [
    {
      "topic_code": "DBMS-608",
      "topic_name": "Boiler Safety",
      "content": "### Overview\\n\\nBoiler safety is **critical**."
    }
  ],
  "suggestions": ["What are alarms?"]
}'''
    tokens = []
    for i in range(0, len(sample_json), 4):
        chunk = sample_json[i:i + 4]
        tokens.extend(extractor.process_chunk(chunk))

    result = "".join(tokens)
    assert result == "### Overview\n\nBoiler safety is **critical**."


def test_stream_extractor_json_multi_section():
    extractor = JsonStreamContentExtractor()
    sample_json = '''{
  "sections": [
    {
      "topic_code": "SEC-1",
      "topic_name": "Part 1",
      "content": "First section content."
    },
    {
      "topic_code": "SEC-2",
      "topic_name": "Part 2",
      "content": "Second section content."
    }
  ],
  "suggestions": []
}'''
    tokens = []
    for i in range(0, len(sample_json), 5):
        chunk = sample_json[i:i + 5]
        tokens.extend(extractor.process_chunk(chunk))

    result = "".join(tokens)
    assert result == "First section content.\n\nSecond section content."


def test_stream_extractor_raw_markdown():
    extractor = JsonStreamContentExtractor()
    sample_md = "### 🏢 1. Company SMS\n\nDirect procedural text."
    tokens = []
    for i in range(0, len(sample_md), 6):
        chunk = sample_md[i:i + 6]
        tokens.extend(extractor.process_chunk(chunk))

    result = "".join(tokens)
    assert result == sample_md


def test_query_node_streaming():
    async def _run():
        mock_openai = MagicMock()
        
        async def mock_stream(*args, **kwargs):
            chunks = [
                '{\n  "sections": [\n    {\n      "topic_code": "T1",\n      "topic_name": "Test",\n      "content": "Hello ',
                'world of ',
                'maritime streaming!"\n    }\n  ],\n  "suggestions": ["Question 1?"]\n}'
            ]
            for c in chunks:
                yield c

        mock_openai.stream_chat = mock_stream
        mock_suggestion = MagicMock()

        state = {
            "current_query": "What is navigation?",
            "standalone_query": "What is navigation?",
            "retrieval_chunks": [
                {
                    "topic_code": "T1",
                    "topic_name": "Test",
                    "content": "Navigation basics in maritime.",
                    "videos": [],
                    "images": [],
                    "pdfs": []
                }
            ],
            "router_decision": {"node_type": "query"},
            "user_profile": {"name": "Officer"}
        }

        streamed_tokens = []
        async def on_token(event):
            if event.get("type") == "content":
                streamed_tokens.append(event.get("token"))

        result_state = await query_node(state, mock_openai, mock_suggestion, on_token=on_token)

        assert "".join(streamed_tokens) == "Hello world of maritime streaming!"
        assert result_state["node_response"]["type"] == "query"
        assert "Hello world of maritime streaming!" in result_state["node_response"]["content"]
        assert len(result_state["node_response"]["sections"]) == 1
        assert result_state["node_response"]["question_suggestions"] == ["Question 1?"]

    asyncio.run(_run())


def test_company_query_node_streaming():
    async def _run():
        mock_openai = MagicMock()
        
        async def mock_stream(*args, **kwargs):
            chunks = [
                "### 🏢 1. Demo Company's Safety Management System (SMS / QMS)\n",
                "**Document Title:** Safety Manual.docx\n\n",
                "Follow strict enclosed space procedures.\n\n",
                "### 📘 2. Dolphin internal knowledge base\n\nStandard rules."
            ]
            for c in chunks:
                yield c

        mock_openai.stream_chat = mock_stream

        state = {
            "current_query": "What is enclosed space entry?",
            "standalone_query": "What is enclosed space entry?",
            "company_chunks": [
                {
                    "document_title": "Safety Manual.docx",
                    "content": "Enclosed space entry safety procedures."
                }
            ],
            "user_profile": {"company_name": "Demo Company", "company_id": "1"}
        }

        streamed_tokens = []
        async def on_token(event):
            if event.get("type") == "content":
                streamed_tokens.append(event.get("token"))

        result_state = await company_query_node(state, mock_openai, on_token=on_token)

        streamed_text = "".join(streamed_tokens)
        assert "Demo Company" in streamed_text
        assert result_state["company_answer"] is not None
        assert result_state["node_response"]["content"] is not None

    asyncio.run(_run())


def test_company_query_node_streaming_no_company_data_suppressed():
    """Verify that when LLM returns NO_COMPANY_DATA during streaming, NO tokens are sent to on_token."""
    async def _run():
        mock_openai = MagicMock()

        async def mock_stream(*args, **kwargs):
            chunks = [
                "NO_COMPANY_DATA",
                "\n\n### Low Flash Point Fuels",
            ]
            for c in chunks:
                yield c

        mock_openai.stream_chat = mock_stream

        state = {
            "current_query": "Describe low flash point fuels used onboard ships",
            "standalone_query": "Describe low flash point fuels used onboard ships",
            "company_chunks": [
                {
                    "document_title": "Ship/Shore Information Exchange.docx",
                    "content": "Cargo loading information exchange procedures."
                }
            ],
            "user_profile": {"company_name": "Demo Company", "company_id": "1"}
        }

        streamed_tokens = []
        async def on_token(event):
            if event.get("type") == "content":
                streamed_tokens.append(event.get("token"))

        result_state = await company_query_node(state, mock_openai, on_token=on_token)

        # Ensure NO tokens were streamed to client
        assert len(streamed_tokens) == 0
        assert result_state["company_answer"] is None

    asyncio.run(_run())


def test_greeting_node_streaming():
    from pipeline.greeting import greeting_node

    async def _run():
        state = {
            "current_query": "hello there!",
            "meaningful_messages": [],
            "meaningful_history": [],
            "user_profile": {"name": "Captain"}
        }

        res = await greeting_node(state)
        assert res["node_response"]["type"] == "greeting"
        assert len(res["node_response"]["content"]) > 0

    asyncio.run(_run())


def test_chat_service_streaming_dispatch():
    from services.chat_service import ChatService
    from unittest.mock import AsyncMock

    async def _run():
        mock_openai = MagicMock()
        mock_openai.chat = AsyncMock(return_value="hello")
        mock_embedder = MagicMock()
        mock_store = MagicMock()
        mock_store.search_with_embeddings = AsyncMock(return_value=[])
        mock_session_service = MagicMock()
        mock_session_service.update_session_messages = AsyncMock(return_value=None)
        mock_session_service.get_session = AsyncMock(return_value={"messages": []})

        # Mock greeting query flow through ChatService
        chat_service = ChatService(
            mock_openai,
            mock_embedder,
            mock_store,
            mock_session_service
        )
        chat_service.vector_store.search_with_embeddings = AsyncMock(return_value=[])
        chat_service.analyzer.classify_for_router = AsyncMock(return_value={"node_type": "greeting"})
        chat_service.rewrite_query = AsyncMock(return_value="hello")
        chat_service.check_query_scope = AsyncMock(return_value="IN-SCOPE")
        chat_service.append_message = AsyncMock(return_value=[{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hello"}])

        streamed_events = []
        async def on_token_cb(event):
            streamed_events.append(event)

        node_response, updated_msgs, sess_id, stand_q, metadata = await chat_service.run_chat(
            user_id="test_user",
            session_id="test_session",
            db_messages=[],
            current_query="hello",
            user_details={"name": "Captain"},
            standalone_query="hello",
            on_token=on_token_cb
        )

        assert node_response.type == "greeting"
        content_events = [e for e in streamed_events if e.get("type") == "content"]
        assert len(content_events) > 0
        assert "".join(e.get("token") for e in content_events) == node_response.content

    asyncio.run(_run())



