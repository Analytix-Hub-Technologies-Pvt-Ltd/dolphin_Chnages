import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # pragma: no cover - ensure local imports
    sys.path.insert(0, str(ROOT))

# Import actual modules first so they are present in sys.modules
import loguru
import pydantic
import pydantic_settings
import openai

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

if "pydantic_settings" not in sys.modules:  # pragma: no cover - settings shim
    class _DummyBaseSettings:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    sys.modules["pydantic_settings"] = type("_DummySettings", (), {"BaseSettings": _DummyBaseSettings})()

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
            return type("r", (), {"data": [type("d", (), {"embedding": [0.0]})()]})

    class AsyncOpenAI:  # pragma: no cover - mimic openai client
        def __init__(self, *_, **__):
            self.chat = _DummyChat()
            self.embeddings = _DummyEmbeddings()

    sys.modules["openai"] = type("_DummyOpenAI", (), {"AsyncOpenAI": AsyncOpenAI})()

from graph.quiz_node import QuizNode


class StubOpenAIService:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    async def chat(self, messages, temperature=None, category=None, **kwargs):  # pragma: no cover - trivial stub
        self.calls.append(messages)
        return self.response


class StubSuggestionService:
    def generate(self, query, chunks, history, short_topic, category=None):  # pragma: no cover - simple stub
        return ["suggestion-1", "suggestion-2"]


def _run(node: QuizNode, state: dict):
    return asyncio.run(node.run(state))


def test_quiznode_builds_deterministic_prompt():
    """Quiz prompts should consistently include rules and supplied content."""

    openai = StubOpenAIService("{}")
    suggestion = StubSuggestionService()
    node = QuizNode(openai, suggestion)

    chunks = [
        {"content": "Marine safety guidelines around signaling. All vessels must maintain proper signaling equipment, including lights, shapes, and sound signals, to ensure collision avoidance under COLREG rules."},
        {"content": "Vessel handling in shallow waters. Shallow water effects include squat, where a ship's draft increases, and reduced rudder efficiency due to restricted water flow around the hull."},
    ]
    state = {
        "router_decision": {"short_topic": "safety", "reason": "route"},
        "retrieval_chunks": chunks,
        "video_suggestions": [],
        "current_query": "Give me a marine safety quiz",
        "messages": [{"role": "user", "content": "Give me a marine safety quiz"}],
        "meaningful_messages": [],
        "meaningful_history": [],
    }

    _run(node, state)

    captured_prompt = openai.calls[0][0]["content"]

    assert "You are a quiz generator" in captured_prompt
    assert "5-question multiple-choice" in captured_prompt
    assert "MARINE COURSE CONTENT:" in captured_prompt
    assert "Marine safety guidelines" in captured_prompt
    assert "Vessel handling in shallow waters" in captured_prompt


def test_quiznode_prompt_is_stable_across_runs():
    """Running the node multiple times should not change the prompt body."""

    openai = StubOpenAIService("{}")
    suggestion = StubSuggestionService()
    node = QuizNode(openai, suggestion)

    chunks = [
        {"content": "Marine safety guidelines around signaling. All vessels must maintain proper signaling equipment, including lights, shapes, and sound signals, to ensure collision avoidance under COLREG rules."},
        {"content": "Vessel handling in shallow waters. Shallow water effects include squat, where a ship's draft increases, and reduced rudder efficiency due to restricted water flow around the hull."},
    ]
    state = {
        "router_decision": {"short_topic": "safety", "reason": "route"},
        "retrieval_chunks": chunks,
        "video_suggestions": [],
        "current_query": "Give me a marine safety quiz",
        "messages": [{"role": "user", "content": "Give me a marine safety quiz"}],
        "meaningful_messages": [],
        "meaningful_history": [],
    }

    expected_prompt = (
        "You are a quiz generator for marine training. Create a 5-question multiple-choice quiz in JSON.\n\n"
        "USER'S QUIZ REQUEST: \"Give me a marine safety quiz\"\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. Generate questions ONLY about the topic requested by the user above\n"
        "2. If the provided content does not contain information about the requested topic, "
        "respond with a single question explaining that a quiz on this specific topic cannot be generated\n"
        "3. Base all questions strictly on the marine content provided below\n"
        "4. Each question must have exactly 4 options\n"
        "5. Use zero-based indexing for correct_index (0, 1, 2, or 3)\n"
        "6. If the provided content does not contain sufficient factual information to create 5 high-quality questions about this topic, respond ONLY with a JSON object containing a single question explaining this.\n\n"
        "OUTPUT FORMAT (valid JSON only, no markdown):\n"
        "{\n"
        "  \"quiz_items\": [\n"
        "    {\n"
        "      \"question\": \"What is...\",\n"
        "      \"options\": [\"A\", \"B\", \"C\", \"D\"],\n"
        "      \"correct_index\": 1\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "MARINE COURSE CONTENT:\n"
        "Marine safety guidelines around signaling. All vessels must maintain proper signaling equipment, including lights, shapes, and sound signals, to ensure collision avoidance under COLREG rules.\n\n---\n\nVessel handling in shallow waters. Shallow water effects include squat, where a ship's draft increases, and reduced rudder efficiency due to restricted water flow around the hull.\n\n"
        'Remember: Generate quiz questions ONLY about "Give me a marine safety quiz" using the content above. Fall back to a single \'insufficient content\' question if necessary.'
    )

    _run(node, state)
    _run(node, state)

    captured_prompts = [call[0]["content"] for call in openai.calls]

    assert captured_prompts[0] == expected_prompt
    assert captured_prompts[1] == expected_prompt


def test_quiznode_falls_back_when_json_is_invalid():
    """If the model returns invalid JSON, the node should supply a default quiz."""

    openai = StubOpenAIService("not-json")
    suggestion = StubSuggestionService()
    node = QuizNode(openai, suggestion)

    chunks = [
        {"content": "Marine navigation systems are critical for ship safety and guidance in open water and narrow channels. Standard navigation systems include GPS, radar, echo sounders, and electronic chart display information systems (ECDIS)."}
    ]
    state = {
        "router_decision": {"short_topic": "navigation", "reason": "route"},
        "retrieval_chunks": chunks,
        "video_suggestions": [],
        "current_query": "Navigation quiz",
        "messages": [{"role": "user", "content": "Navigation quiz"}],
        "meaningful_messages": [],
        "meaningful_history": [],
    }

    result = _run(node, state)
    content = result["node_response"]["content"]

    assert content["type"] == "quiz"
    assert content["quiz_items"]
    fallback = content["quiz_items"][0]
    assert fallback["question"] == "I couldn't generate a quiz based on the available content. Would you like to ask about a specific marine topic first?"
    assert fallback["options"] == [
        "Yes, tell me about Port State Control",
        "Yes, explain fatigue management",
        "Yes, describe RightShip audits",
        "Show me available topics",
    ]
    assert fallback["correct_index"] == 0
