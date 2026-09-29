import asyncio
from unittest.mock import AsyncMock, MagicMock

from services.query_analyzer import QueryAnalyzer, EnhancedQueryAnalyzer
from services.gpt_intent_service import GPTIntentService
from pipeline.company_retrieval import company_retrieval_node
from pipeline.company_query import company_query_node
from pipeline.well_wish import well_wish_node
from pipeline.greeting import greeting_node
from pipeline.fallback import fallback_node
from services.scope_messages import is_out_of_scope_text


def test_simple_intent_fast_path_casual():
    """Test fast-path recognition for casual queries like 'are you doing?' and 'who are you?'."""
    analyzer = QueryAnalyzer(GPTIntentService())

    # Well wishes / status checks
    assert analyzer._is_simple_intent("are you doing") == "WELL_WISH"
    assert analyzer._is_simple_intent("are you doing?") == "WELL_WISH"
    assert analyzer._is_simple_intent("how are you doing?") == "WELL_WISH"
    assert analyzer._is_simple_intent("what are you doing?") == "WELL_WISH"
    assert analyzer._is_simple_intent("how r u") == "WELL_WISH"
    assert analyzer._is_simple_intent("how is it going?") == "WELL_WISH"
    assert analyzer._is_simple_intent("how are things?") == "WELL_WISH"

    # Bot identity / capability inquiries
    assert analyzer._is_simple_intent("who are you?") == "GREETING"
    assert analyzer._is_simple_intent("what are you") == "GREETING"
    assert analyzer._is_simple_intent("what is dolphin ai?") == "GREETING"
    assert analyzer._is_simple_intent("what can you do?") == "GREETING"
    assert analyzer._is_simple_intent("introduce yourself") == "GREETING"
    assert analyzer._is_simple_intent("tell me about yourself") == "GREETING"

    # Actual maritime queries should return None so they undergo full processing
    assert analyzer._is_simple_intent("explain snap back zone") is None
    assert analyzer._is_simple_intent("what is anchor watch?") is None
    assert analyzer._is_simple_intent("enclosed space entry procedure") is None


def test_is_obvious_query_does_not_falsely_match_casual_questions():
    """Test that ? in casual queries does not bypass intent classification."""
    analyzer = QueryAnalyzer(GPTIntentService())

    # Casual queries with question marks should NOT be treated as obvious domain queries
    assert analyzer._is_obvious_query("are you doing?") is False
    assert analyzer._is_obvious_query("how are you?") is False
    assert analyzer._is_obvious_query("who are you?") is False
    assert analyzer._is_obvious_query("what are you doing?") is False

    # Genuine maritime domain queries with question marks SHOULD be recognized
    assert analyzer._is_obvious_query("what is anchor watch?") is True
    assert analyzer._is_obvious_query("explain snap back zone") is True
    assert analyzer._is_obvious_query("procedure for bunkering") is True


def test_enhanced_query_analyzer_router_casual_and_out_of_scope():
    """Test router classification for casual and out-of-scope queries."""
    mock_intent = AsyncMock()
    mock_intent.classify_intent = AsyncMock(return_value="OUT_OF_SCOPE")

    analyzer = EnhancedQueryAnalyzer(mock_intent)

    # 1. Fast-path casual query
    decision_casual = asyncio.run(analyzer.classify_for_router("are you doing?", []))
    assert decision_casual["node_type"] == "well_wish"
    assert decision_casual["category"] == "WELL_WISH"

    # 2. Fast-path identity query
    decision_identity = asyncio.run(analyzer.classify_for_router("who are you?", []))
    assert decision_identity["node_type"] == "greeting"
    assert decision_identity["category"] == "GREETING"

    # 3. Out of scope query
    decision_oos = asyncio.run(analyzer.classify_for_router("how to bake chocolate cake", []))
    assert decision_oos["node_type"] == "fallback"
    assert decision_oos["category"] == "OUT_OF_SCOPE"


def test_company_retrieval_returns_empty_for_casual_queries():
    """Verify company_retrieval_node does not return irrelevant company chunks on casual questions."""
    mock_store = MagicMock()
    mock_store.search_with_embeddings = AsyncMock(return_value=[
        {
            "company_id": "comp_123",
            "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx",
            "topic_name": "Voyage Planning General",
            "content": "Master must establish a detailed plan for the entire voyage.",
            "_score": 1.0,  # FAISS L2 distance
            "_faiss_index": 0,
        }
    ])
    mock_store.search_bm25 = MagicMock(return_value=[])

    state = {
        "current_query": "are you doing?",
        "standalone_query": "are you doing?",
        "user_profile": {
            "company_id": "comp_123",
            "company_name": "Demo Company",
            "ship_type": "Chemical Tanker",
        },
    }

    result = asyncio.run(company_retrieval_node(state, mock_store))
    assert result.get("company_chunks") == []


def test_company_query_node_guards_against_unrelated_queries():
    """Verify company_query_node sets company_answer = None when chunks are unrelated to query."""
    mock_openai = AsyncMock()

    state = {
        "current_query": "are you doing?",
        "standalone_query": "are you doing?",
        "user_profile": {
            "company_id": "comp_123",
            "company_name": "Demo Company",
            "role": "Master",
            "ship_type": "Chemical Tanker",
        },
        "company_chunks": [
            {
                "topic_name": "Voyage Planning General",
                "document_title": "Shipboard SMS Manual",
                "content": "Establish a detailed plan for the entire voyage | Master",
            }
        ],
    }

    result = asyncio.run(company_query_node(state, mock_openai))
    # Must not call LLM and must not output company_answer
    assert result.get("company_answer") is None
    assert not mock_openai.chat.called


def test_well_wish_node_response():
    """Verify well_wish_node returns a clean, polite response with no media leaks."""
    state = {
        "current_query": "are you doing?",
        "user_profile": {"name": "Captain John"},
        "router_decision": {"node_type": "well_wish", "category": "WELL_WISH", "reason": "well_wish"},
    }

    result = asyncio.run(well_wish_node(state))
    resp = result["node_response"]
    assert resp["type"] == "well_wish"
    assert "doing well" in resp["content"]
    assert "Captain John" in resp["content"]
    assert resp["videos"] == []
    assert resp["images"] == []
    assert resp["metadata"]["category"] == "WELL_WISH"


def test_greeting_node_identity_response():
    """Verify greeting_node returns an informative introduction when asked about bot identity."""
    state = {
        "current_query": "who are you?",
        "user_profile": {},
        "router_decision": {"node_type": "greeting", "category": "GREETING", "reason": "greeting"},
    }

    result = asyncio.run(greeting_node(state))
    resp = result["node_response"]
    assert resp["type"] == "greeting"
    assert "Dolphin AI" in resp["content"]
    assert resp["videos"] == []


def test_fallback_node_out_of_scope():
    """Verify fallback_node returns a standard out-of-scope message for non-marine queries."""
    mock_sugg = MagicMock()

    state = {
        "current_query": "what is the recipe for chocolate cake?",
        "router_decision": {"node_type": "fallback", "category": "OUT_OF_SCOPE", "reason": "out_of_scope"},
        "retrieval_chunks": [],
        "messages": [],
    }

    result = asyncio.run(fallback_node(state, mock_sugg))
    resp = result["node_response"]
    assert resp["type"] == "fallback"
    assert is_out_of_scope_text(resp["content"])
    assert resp["chunks_used"] == []
    assert resp["videos"] == []
    assert resp["metadata"]["category"] == "OUT_OF_SCOPE"
