import asyncio
import pathlib
import sys

import pytest

from services.embedding_config import EMBEDDING_DIM

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(ROOT))

# Import actual modules first so they are present in sys.modules
import loguru
import pydantic
import pydantic_settings
import openai
import faiss
import numpy

if "loguru" not in sys.modules:  # pragma: no cover - lightweight logger shim
    class _DummyLogger:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    sys.modules["loguru"] = type("_Dummy", (), {"logger": _DummyLogger()})()

if "pydantic" not in sys.modules:  # pragma: no cover - minimal BaseModel shim
    class _DummyBaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_dump(self):
            return self.__dict__

        @classmethod
        def model_validate(cls, data):
            if isinstance(data, cls):
                return data
            if isinstance(data, dict):
                return cls(**data)
            raise TypeError("Invalid data for model_validate")

    def _dummy_field(default=None, default_factory=None, **kwargs):
        if default_factory is not None:
            try:
                return default_factory()
            except TypeError:
                return default_factory
        return default

    sys.modules["pydantic"] = type(
        "_DummyPydantic", (), {"BaseModel": _DummyBaseModel, "Field": _dummy_field}
    )()

if "openai" not in sys.modules:  # pragma: no cover - simple async client stub
    class _DummyChoice:
        def __init__(self, content=""):
            self.message = type("m", (), {"content": content})
            self.finish_reason = "stop"

    class _DummyChat:
        class completions:  # pragma: no cover - compatibility
            @staticmethod
            async def create(model=None, temperature=None, messages=None):
                return type("r", (), {"choices": [_DummyChoice()]})

    class _DummyEmbeddings:
        @staticmethod
        async def create(model=None, input=None):
            return type("r", (), {"data": [type("d", (), {"embedding": [0.0] * EMBEDDING_DIM})()]})

    class AsyncOpenAI:  # pragma: no cover - mimic openai client
        def __init__(self, *_, **__):
            self.chat = _DummyChat()
            self.embeddings = _DummyEmbeddings()

    sys.modules["openai"] = type("_DummyOpenAI", (), {"AsyncOpenAI": AsyncOpenAI})()

if "pydantic_settings" not in sys.modules:  # pragma: no cover - settings shim
    class _DummyBaseSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    sys.modules["pydantic_settings"] = type("_DummySettings", (), {"BaseSettings": _DummyBaseSettings})()

if "faiss" not in sys.modules:  # pragma: no cover - FAISS shim
    class _DummyIndex:
        def __init__(self, dimension=0):
            self.ntotal = 0

        def add(self, embeddings):
            try:
                self.ntotal += len(embeddings)
            except TypeError:
                self.ntotal += 1

        def search(self, query_vector, k):
            return [], [[0 for _ in range(k)]]

    sys.modules["faiss"] = type(
        "_DummyFaiss",
        (),
        {
            "IndexFlatL2": _DummyIndex,
            "write_index": lambda *_, **__: None,
            "read_index": lambda *_, **__: _DummyIndex(),
        },
    )()

if "numpy" not in sys.modules:  # pragma: no cover - lightweight numpy shim
    class _DummyArray(list):
        def astype(self, dtype):
            return self

    numpy_stub = type("_DummyNumpy", (), {})()
    numpy_stub.array = lambda obj, dtype=None: _DummyArray(obj)
    numpy_stub.float32 = "float32"
    sys.modules["numpy"] = numpy_stub

if "langgraph.graph" not in sys.modules:  # pragma: no cover - graph shim
    END = "__END__"

    class _DummyStateGraph:
        def __init__(self, state_type=None):
            self._nodes = {}
            self._edges = {}
            self._conditional = {}
            self.entrypoint = None

        def add_node(self, name, fn):
            self._nodes[name] = fn

        def set_entrypoint(self, name):
            self.entrypoint = name

        def set_entry_point(self, name):  # backward compatibility
            self.entrypoint = name

        def add_conditional_edges(self, node, fn, mapping):
            self._conditional[node] = (fn, mapping)

        def add_edge(self, src, dest):
            self._edges[src] = dest

        def compile(self):
            parent = self

            class _CompiledGraph:
                def __init__(self, graph):
                    self.graph = graph

                async def ainvoke(self, state):
                    class _StateWrapper(dict):
                        def __init__(self, data):
                            super().__init__(data)
                            for key, value in data.items():
                                setattr(self, key, value)

                        def update(self, updates):
                            super().update(updates)
                            for key, value in updates.items():
                                setattr(self, key, value)

                    wrapper = _StateWrapper(state if isinstance(state, dict) else {})
                    current = parent.entrypoint

                    while current and current != END:
                        node_fn = parent._nodes[current]
                        updates = await node_fn(wrapper)
                        wrapper.update(updates or {})

                        if current in parent._conditional:
                            cond_fn, mapping = parent._conditional[current]
                            next_key = cond_fn(wrapper)
                            current = mapping.get(next_key, parent._edges.get(current))
                        else:
                            current = parent._edges.get(current)

                    return wrapper

            return _CompiledGraph(self)

    sys.modules["langgraph.graph"] = type(
        "_DummyLangGraph", (), {"StateGraph": _DummyStateGraph, "END": END}
    )()

from graph.query_node import QueryNode
from graph.retrieval_node import RetrievalNode
from graph.fallback_node import FallbackNode
from models.node_response import NodeResponse
from services.chat_service import ChatService
from services.query_analyzer import EnhancedQueryAnalyzer


class StubOpenAIService:
    def __init__(self):
        self.calls = []

    async def chat(self, messages, temperature=None, category=None, **kwargs):
        self.calls.append(messages)
        # Echo back the prompt content for inspection
        return messages[0]["content"] if messages else ""


class StubSuggestionService:
    def generate(self, query, chunks, history, short_topic, category=None):  # pragma: no cover - simple stub
        return ["suggestion-1", "suggestion-2"]


def _run_async(coro):
    return asyncio.run(coro)


class StubVectorStore:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    async def search_with_embeddings(self, query, k=4):
        self.calls.append((query, k))
        return list(self.chunks)


class StubEmbedder:
    async def embed_query(self, query):  # pragma: no cover - trivial stub
        return [0.0] * EMBEDDING_DIM


def test_retrieval_populates_chunks():
    chunks = [
        {
            "content_id": 1,
            "topic_name": "Anchoring",
            "topic_content": "Anchoring basics",
            "content": "Topic Name: Anchoring\n\nTopic Content:\nAnchoring basics",
            "videos": [],
            "images": [],
            "pdfs": [],
        },
        {
            "content_id": 2,
            "topic_name": "Scope",
            "topic_content": "Scope ratio",
            "content": "Topic Name: Scope\n\nTopic Content:\nScope ratio",
            "videos": [],
            "images": [],
            "pdfs": [],
        },
    ]
    vector_store = StubVectorStore(chunks)
    retrieval = RetrievalNode(vector_store)

    initial_state = {
        "current_query": "Explain anchoring",
        "meaningful_messages": [{"node_type": "query", "content": "previous"}],
        "meaningful_history": [{"node_type": "query", "content": "previous"}],
    }

    updates = _run_async(
        retrieval.run(initial_state)
    )
    assert len(updates["retrieval_chunks"]) == 2
    assert updates["retrieval_chunks"][0]["content"].startswith("Topic Name: Anchoring")
    assert "meaningful_messages" in updates
    assert "meaningful_history" in updates

    # Ensure downstream QueryNode can see the chunks
    combined_state = {**initial_state, **updates, "router_decision": {"node_type": "query", "reason": "t", "short_topic": "anchor"}}
    query_node = QueryNode(StubOpenAIService(), StubSuggestionService())
    result = _run_async(
        query_node.run(combined_state)
    )

    assert result["node_response"]["chunks_used"][0]["content"].startswith("Topic Name: Anchoring")
    assert result["meaningful_messages"]


def test_querynode_receives_chunks_and_history():
    openai = StubOpenAIService()
    suggestion = StubSuggestionService()
    query_node = QueryNode(openai, suggestion)

    state = {
        "current_query": "What is scope ratio?",
        "router_decision": {"node_type": "query", "short_topic": "scope", "reason": "route"},
        "retrieval_chunks": [
            {
                "topic_name": "Scope Ratios",
                "topic_content": "Scope ratio details",
                "content": "Topic Name: Scope Ratios\n\nTopic Content:\nScope ratio details",
                "videos": [],
                "images": [],
                "pdfs": [],
            }
        ],
        "video_suggestions": [],
        "session_messages": [
            {"role": "assistant", "content": "Anchoring basics", "category": "SUMMARY"},
            {"role": "user", "content": "Explain anchors", "category": "QUERY"},
        ],
        "meaningful_messages": [
            {"node_type": "query", "content": "Anchoring basics"},
            {"node_type": "greeting", "content": "Hello"},
        ],
        "meaningful_history": [
            {"node_type": "summary", "content": "Summary of anchoring"}
        ],
    }

    result = _run_async(query_node.run(state))
    captured_prompt = openai.calls[-1][0]["content"]

    assert "Scope ratio details" in captured_prompt
    assert result["node_response"]["metadata"]["short_topic"] == "scope"
    assert result["node_response"]["metadata"]["routing_reason"] == "route"


def test_querynode_preserves_history_with_type_key():
    """Repeated queries with prior history entries should trigger conversation context in the prompt."""

    openai = StubOpenAIService()
    suggestion = StubSuggestionService()
    query_node = QueryNode(openai, suggestion)

    state = {
        "current_query": "How does ballast work?",
        "router_decision": {"node_type": "query", "short_topic": "ballast", "reason": "route"},
        "retrieval_chunks": [{"title": "Ballast", "content": "Ballast basics"}],
        "video_suggestions": [],
        "session_messages": [
            {
                "role": "assistant",
                "content": "Ballast keeps stability",
                "category": "QUERY",
            },
            {"role": "user", "content": "How does ballast work?", "category": "QUERY"},
        ],
        "meaningful_messages": [
            {
                "type": "query",
                "content": "Ballast keeps stability",
                "user_query": "How does ballast work?",
            }
        ],
        "meaningful_history": [],
    }

    _ = _run_async(query_node.run(state))
    captured_prompt = openai.calls[-1][0]["content"]

    assert "Ballast basics" in captured_prompt
    assert "Ballast keeps stability" in captured_prompt
    assert "PREVIOUS COVERAGE" in captured_prompt


def test_chatservice_graph_flow(monkeypatch):
    # Force router to select query path
    async def mock_classify(self, query, previous_questions):
        return {"node_type": "query", "short_topic": "marine", "reason": "analysis"}

    monkeypatch.setattr(
        EnhancedQueryAnalyzer,
        "classify_for_router",
        mock_classify,
    )
    
    async def mock_scope(self, query, chunks):
        return "IN-SCOPE"
        
    monkeypatch.setattr(
        ChatService,
        "check_query_scope",
        mock_scope,
    )

    vector_store = StubVectorStore([
        {"title": "Hull", "content": "Hull design details", "video_id": "vh1"}
    ])

    service = ChatService(StubOpenAIService(), StubEmbedder(), vector_store)

    response, updated_messages, *rest = _run_async(
        service.run_chat("user-1", "session-1", [{"question": "Hi"}], "Explain hull design")
    )

    assert isinstance(response, NodeResponse)
    assert response.metadata["short_topic"] == "marine"
    assert response.metadata["routing_reason"] == "analysis"
    assert response.chunks_used

    # Validate updated messages include assistant entry with unified schema
    assistant_content = updated_messages[-1]
    assert assistant_content["role"] == "assistant"
    assert assistant_content["content"]
    assert assistant_content["category"]
    assert "question" not in assistant_content
    assert "response" not in assistant_content
    assert assistant_content.get("question_suggestions") is not None
    assert isinstance(assistant_content.get("video_suggestions"), list)

    for msg in updated_messages:
        assert isinstance(msg, dict)
        assert "category" in msg
        assert msg.get("content") is not None

    state = service._last_state or {}
    assert len(state.get("retrieval_chunks", [])) == 1
    assert state.get("messages") and state["messages"][-1]["role"] == "assistant"


def test_node_response_validation():
    data = {
        "type": "query",
        "content": "answer",
        "chunks_used": [{"content": "c1"}],
        "video_suggestions": [],
        "question_suggestions": ["q1"],
        "metadata": {"short_topic": "marine", "routing_reason": "query"},
    }

    validated = NodeResponse.model_validate(data)
    assert validated.metadata["short_topic"] == "marine"
    assert validated.metadata["routing_reason"] == "query"


def test_company_query_cow_checklist():
    from pipeline.company_query import company_query_node

    class MockOpenAIService:
        async def chat(self, messages, temperature=0.0):
            return """
### 🏢 1. According to CMS Demo Company's Safety Management System (SMS / QMS)
**Document Title:** Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx
**SOP Name:** Crude Oil Washing (COW) Procedures
**Section:** COW Checklist

Confirm all pre-arrival checks are performed [ ] [ ] 

### 📘 2. Dolphin internal knowledge base
Dolphin info.
"""

    state = {
        "company_chunks": [{"document_title": "Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx", "content": "Confirm all pre-arrival checks"}],
        "user_profile": {"company_name": "CMS Demo Company"},
        "standalone_query": "What is the COW checklist?",
        "node_response": {}
    }

    updated_state = asyncio.run(company_query_node(state, MockOpenAIService()))
    answer = updated_state["company_answer"]

    assert "COW Entry and Cleaning Checklist" in answer
    assert "**Section:** COW Checklist" in answer
    assert "1. Confirm all pre-arrival checks are performed" in answer
    assert "| 1. Confirm all pre-arrival checks are performed |  |  | R | |" in answer
    assert "Dolphin info." in answer


def test_is_company_query():
    from pipeline.company_query import is_company_query
    
    # Company related
    assert is_company_query("What is the company SMS procedure for anchor watch?", "CMS Demo Company") is True
    assert is_company_query("Do we have a checklist for anchoring?", "CMS Demo Company") is True
    assert is_company_query("What is the SOP on CMS Demo Company?", "CMS Demo Company") is True
    assert is_company_query("What is on my vessel?", "CMS Demo Company") is True
    assert is_company_query("explain handling of cargo", "CMS Demo Company") is True
    assert is_company_query("handling of cargo", "CMS Demo Company") is True
    assert is_company_query("Instructions to ship's staff", "CMS Demo Company") is True
    assert is_company_query("Instructions to ship‘s staff", "CMS Demo Company") is True
    
    # General queries
    assert is_company_query("what is anchor", "CMS Demo Company") is False
    assert is_company_query("what is the definition of stockless anchor", "CMS Demo Company") is False
    assert is_company_query("explain ship stability in general", "CMS Demo Company") is False


def test_company_query_skipped_for_general_queries():
    from pipeline.company_query import company_query_node

    class MockOpenAIService:
        async def chat(self, messages, temperature=0.0):
            return "Should not be called"

    state = {
        "company_chunks": [{"document_title": "Shipboard SMS Manual (Vol. II)-Oil Tanker 2016.docx", "content": "Confirm all pre-arrival checks"}],
        "user_profile": {"company_name": "CMS Demo Company"},
        "standalone_query": "what is anchor",
        "node_response": {"content": "General answer from query_node"}
    }

    updated_state = asyncio.run(company_query_node(state, MockOpenAIService()))
    assert updated_state["company_answer"] is None
    assert updated_state["node_response"]["content"] == "General answer from query_node"


def test_greeting_intent_classification_variations():
    import pytest
    from services.query_analyzer import EnhancedQueryAnalyzer
    from services.gpt_intent_service import GPTIntentService

    # Use a dummy intent service that raises a failure if it's called
    class DummyIntentService(GPTIntentService):
        def __init__(self):
            pass
        async def classify_intent(self, message: str) -> str:
            pytest.fail(f"GPTIntentService.classify_intent should not be called for fast-path: {message}")

    analyzer = EnhancedQueryAnalyzer(DummyIntentService())
    
    # Test cases that should hit the fast-path as GREETING
    greetings = ["hi", "hii", "hiii", "hello", "helloo", "hellooo", "hey", "heyy", "yoo", "yo", "hola", "holaa"]
    for g in greetings:
        decision = asyncio.run(analyzer.classify_for_router(g, []))
        assert decision["category"] == "GREETING", f"Failed for greeting: {g}"
        assert decision["node_type"] == "greeting", f"Failed for node_type: {g}"

    # Test cases that should hit the fast-path as GOODBYE
    goodbyes = ["bye", "byee"]
    for b in goodbyes:
        decision = asyncio.run(analyzer.classify_for_router(b, []))
        assert decision["category"] == "GOODBYE", f"Failed for goodbye: {b}"
        assert decision["node_type"] == "goodbye", f"Failed for node_type: {b}"

    # Test cases that should hit the fast-path as THANK
    thanks = ["thanks", "thanks a lot", "thx"]
    for t in thanks:
        decision = asyncio.run(analyzer.classify_for_router(t, []))
        assert decision["category"] == "THANK", f"Failed for thank: {t}"
        assert decision["node_type"] == "thank", f"Failed for node_type: {t}"


def test_querynode_out_of_scope():
    openai = StubOpenAIService()
    suggestion = StubSuggestionService()
    query_node = QueryNode(openai, suggestion)
    
    # 1. Test out-of-scope unrelated query (classification is UNRELATED or TANGENTIALLY_RELATED)
    state = {
        "current_query": "How do I create an array in Python?",
        "router_decision": {"node_type": "query", "short_topic": "python", "reason": "route"},
        "retrieval_chunks": [],
        "video_suggestions": [],
        "session_messages": [],
        "meaningful_messages": [],
        "meaningful_history": [],
    }
    
    result = _run_async(query_node.run(state))
    assert result["node_response"]["content"] == "This is not part of the available course material. Please ask a question related to the Marine/Maritime course content."
    assert result["node_response"]["question_suggestions"] == []
    
    # 2. Test Titanic query (Titanic terms not in chunks)
    state_titanic = {
        "current_query": "How did Titanic sink?",
        "router_decision": {"node_type": "query", "short_topic": "titanic", "reason": "route"},
        "retrieval_chunks": [{"title": "Ship Sinking General", "content": "Water ingress can cause vessels to lose stability."}],
        "video_suggestions": [],
        "session_messages": [],
        "meaningful_messages": [],
        "meaningful_history": [],
    }
    
    result_titanic = _run_async(query_node.run(state_titanic))
    assert result_titanic["node_response"]["content"] == "This is not part of the available course material. Please ask a question related to the Marine/Maritime course content."
    assert result_titanic["node_response"]["question_suggestions"] == []


def test_fallbacknode_out_of_scope():
    suggestion = StubSuggestionService()
    fallback_node = FallbackNode(suggestion)
    
    state = {
        "current_query": "What is the capital of France?",
        "router_decision": {"node_type": "fallback", "short_topic": "general", "reason": "fallback"},
        "retrieval_chunks": [],
        "previous_questions": [],
        "messages": [],
    }
    
    result = _run_async(fallback_node.run(state))
    assert result["node_response"]["content"] == "This is not part of the available course material. Please ask a question related to the Marine/Maritime course content."
    assert result["node_response"]["question_suggestions"] == []




