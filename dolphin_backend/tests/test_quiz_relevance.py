import asyncio
import json
import pathlib
import sys
from unittest.mock import MagicMock

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Mock loguru
mock_logger = MagicMock()
sys.modules["loguru"] = MagicMock(logger=mock_logger)

if "openai" not in sys.modules:
    sys.modules["openai"] = MagicMock()

if "config" not in sys.modules:
    sys.modules["config"] = MagicMock(settings=MagicMock())

if "asyncpg" not in sys.modules:
    sys.modules["asyncpg"] = MagicMock()

# Mock the entire models and services that hit DB or external APIs
sys.modules["models.database"] = MagicMock(get_pool=MagicMock())
sys.modules["retrieval.postgres_loader"] = MagicMock()

from graph.quiz_node import QuizNode
from graph.retrieval_node import RetrievalNode

class StubOpenAIService:
    def __init__(self, response: str = "{}"):
        self.response = response
        self.calls = []
    async def chat(self, messages, temperature=None, category=None):
        self.calls.append(messages)
        return self.response

async def test_retrieval_filters_low_confidence_quiz_chunks():
    # Setup RetrievalNode with mock vector store
    mock_vs = MagicMock()
    # High score = low confidence
    mock_vs.search_with_embeddings = MagicMock(return_value=[
        {"_score": 2.5, "content": "Irrelevant content", "topic_name": "Out of scope"}
    ])
    node = RetrievalNode(mock_vs)
    
    state = {
        "current_query": "quiz on rocket science",
        "router_decision": {"node_type": "quiz", "category": "QUIZ", "standalone_query": "quiz on rocket science"},
        "meaningful_messages": [],
        "meaningful_history": []
    }
    
    result = await node.run(state)
    assert len(result["retrieval_chunks"]) == 0
    print("✅ RetrievalNode successfully filtered low-confidence chunks for quiz")

async def test_retrieval_skips_faiss_for_generic_quiz():
    mock_vs = MagicMock()
    node = RetrievalNode(mock_vs)
    
    state = {
        "current_query": "generate quiz",
        "router_decision": {"node_type": "quiz", "category": "QUIZ", "standalone_query": "generate quiz"},
        "meaningful_messages": [],
        "meaningful_history": []
    }
    
    result = await node.run(state)
    mock_vs.search_with_embeddings.assert_not_called()
    assert result["resolved_quiz_topic"] == ""
    print("✅ RetrievalNode successfully skipped FAISS for generic quiz")

async def test_quiz_node_refusal_on_insufficient_content():
    openai = StubOpenAIService()
    suggestion = MagicMock()
    node = QuizNode(openai, suggestion)
    
    # Empty chunks
    state = {
        "current_query": "quiz on Port State Control",
        "resolved_quiz_topic": "Port State Control",
        "retrieval_chunks": [],
        "video_suggestions": [],
        "messages": [],
        "router_decision": {"node_type": "quiz"}
    }
    
    result = await node.run(state)
    openai.chat.assert_not_called() # Should not call LLM if content < 100 chars
    assert "insufficient_content" in result["node_response"]["metadata"]["routing_reason"]
    assert "I couldn't find enough specific information" in result["node_response"]["content"]["quiz_items"][0]["question"]
    print("✅ QuizNode successfully returned refusal for insufficient content")

async def run_tests():
    try:
        await test_retrieval_filters_low_confidence_quiz_chunks()
        await test_retrieval_skips_faiss_for_generic_quiz()
        await test_quiz_node_refusal_on_insufficient_content()
        print("\nALL RELEVANCE TESTS PASSED")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_tests())
