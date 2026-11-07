"""Isolated tests for the "did you mean...?" clarification flow (no DB / OpenAI)."""
import asyncio
import json

import pytest

from services.clarification_service import ClarificationService, parse_general_overview, GENERAL_OVERVIEW_PREFIX, is_definitional_question, definitional_term

TOPICS = [
    "Cargo Temperature Control",
    "Engine Cooling Water Temperature",
    "Reefer Container Temperature Monitoring",
    "Enclosed Space Entry",
    "Fire Fighting Basics",
    "Ballast Water Management",
]


def chunk(name, code="", body="", **extra):
    return {"topic_name": name, "topic_code": code, "topic_content": body, **extra}


def run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


@pytest.fixture
def svc():
    return ClarificationService(openai_service=None, use_llm=False)


# ---- eligibility -----------------------------------------------------------
@pytest.mark.parametrize("q", ["temperature", "Temperature?", "what is temperature", "tell me about temperatures"])
def test_bare_terms_are_underspecified(svc, q):
    assert svc.is_underspecified(q)


@pytest.mark.parametrize("q", [
    "how do I control cargo temperature in a reefer hold",
    "SOLAS chapter 2",
    "temperature of regulation 19",
    "hi",
    "",
])
def test_specific_or_empty_queries_are_not(svc, q):
    assert not svc.is_underspecified(q)


# ---- decision --------------------------------------------------------------
def test_temperature_triggers_clarification(svc):
    chunks = [chunk("Engine Cooling Water Temperature", "T2"), chunk("Cargo Temperature Control", "T1")]
    clar = run(svc.maybe_clarify("temperature", chunks, TOPICS))
    assert clar is not None
    kinds = [o.kind for o in clar.options]
    assert kinds[-2:] == ["general", "other"]
    labels = [o.label for o in clar.options if o.kind == "topic"]
    assert labels[0] == "Engine Cooling Water Temperature"      # retrieval order wins
    assert len(labels) == 3 and len(clar.options) == 5
    assert [o.id for o in clar.options] == [1, 2, 3, 4, 5]
    assert not any("DBMV" in l for l in labels)
    assert "Temperature" in clar.question
    # every clickable query must be specific enough to skip a second clarification
    for o in clar.options:
        if o.kind != "other":
            assert len(o.query.split()) >= 3
    assert len(clar.suggestion_queries()) == 3
    assert "1. **[Engine Cooling Water Temperature]" in clar.render_text()


def test_single_matching_topic_is_not_ambiguous(svc):
    assert run(svc.maybe_clarify("ballast", [chunk("Ballast Water Management")], TOPICS)) is None


def test_exact_topic_name_does_not_hide_other_topics(svc):
    # a topic literally called "Temperature" must not stop us asking when 3 others share the word
    topics = ["Temperature", "Cargo Temperature Control", "Engine Cooling Water Temperature", "Reefer Temperature Alarms"]
    chunks = [chunk(n) for n in topics]
    clar = run(svc.maybe_clarify("temperature", chunks, topics))
    assert clar is not None


def test_exact_topic_alone_is_answered_directly(svc):
    assert run(svc.maybe_clarify("temperature", [chunk("Temperature")], ["Temperature", "Boilers"])) is None


def test_labels_are_cleaned_and_deduplicated(svc):
    topics = ["1. Safety Management System-SMS", "Safety Management System - SMS",
              "DBMV-8121-SMS-Prevention of Fire on Bulk Carriers", "SMS Internal Audits"]
    chunks = [chunk(n) for n in topics]
    clar = run(svc.maybe_clarify("SMS", chunks, topics))
    labels = [o.label for o in clar.options if o.kind == "topic"]
    assert all(not l.startswith(("1.", "DBMV")) for l in labels)
    assert len({l.lower().replace(" ", "").replace("-", "") for l in labels}) == len(labels)


def test_similar_topics_are_grouped_into_distinct_options(svc):
    topics = ["Vapor pressure/temperature relationship", "Pressure and Temperature",
              "Saturated vapour pressure/reference temperature", "Temperature Measurements",
              "Vessel performance in ice and low air temperature"]
    clar = run(svc.maybe_clarify("temperature", [chunk(n) for n in topics], topics))
    topic_opts = [o for o in clar.options if o.kind == "topic"]
    assert len(topic_opts) == 3
    assert any("related topic" in o.hint for o in topic_opts)   # the pressure family collapsed into one


def test_long_labels_are_shortened(svc):
    name = "Resistance temperature Detector -RTD - Thermistor - Thermocouple and Optical Pyrometer"
    topics = [name, "Temperature Measurements", "Cargo Temperature Control"]
    clar = run(svc.maybe_clarify("temperature", [chunk(n) for n in topics], topics))
    assert all(len(o.label) <= 60 for o in clar.options)


def test_sme_approved_answer_wins(svc):
    chunks = [chunk("SME Approved Guidance", _is_sme_approved=True), chunk("Cargo Temperature Control")]
    assert run(svc.maybe_clarify("temperature", chunks, TOPICS)) is None


def test_question_is_conversational(svc):
    clar = run(svc.maybe_clarify("temperature", [chunk(n) for n in TOPICS[:3]], TOPICS))
    q = clar.question.lower()
    assert "?" in q and any(w in q for w in ("happy to help", "sure", "good one"))


def test_bare_acronym_is_clarified_from_course_content(svc):
    topics = [
        "Introduction to Safety Management System (SMS)",
        "SMS Internal Audits",
        "Roles and Responsibilities under the ISM Code",
    ]
    chunks = [
        chunk(topics[0], "S1", "The SMS is a structured system..."),
        chunk(topics[1], "S2", "Audits verify the SMS is implemented."),
        chunk(topics[2], "S3", "The Designated Person ensures the Safety Management System works."),
    ]
    clar = run(svc.maybe_clarify("SMS", chunks, topics))
    assert clar is not None
    assert "Safety Management System" in clar.question          # spelled out from the course text
    assert [o.topic_name for o in clar.options if o.kind == "topic"][:2] == topics[:2]
    # topic that only uses the spelled-out form is still offered
    assert any(o.topic_name == topics[2] for o in clar.options)


def test_acronym_with_single_topic_is_answered_directly(svc):
    topics = ["Introduction to Safety Management System (SMS)"]
    assert run(svc.maybe_clarify("SMS", [chunk(topics[0])], topics)) is None


def test_disabled_flag(svc):
    svc.enabled = False
    assert run(svc.maybe_clarify("temperature", [], TOPICS)) is None


def test_previous_topic_is_listed_first(svc):
    chunks = [chunk("Engine Cooling Water Temperature", "T2"), chunk("Cargo Temperature Control", "T1")]
    clar = run(svc.maybe_clarify("temperature", chunks, TOPICS, history_topic_codes=["T1"]))
    assert clar.options[0].label == "Cargo Temperature Control"


def test_content_only_ambiguity_needs_two_topics(svc):
    topics = ["Boilers", "Pumps", "Purifiers"]
    body = "Keep the temperature within limits."
    one = [chunk("Boilers", body=body)]
    two = one + [chunk("Pumps", body=body)]
    assert run(svc.maybe_clarify("temperature", one, topics)) is None
    assert run(svc.maybe_clarify("temperature", two, topics)) is not None


def test_one_named_topic_plus_content_mentions_elsewhere_still_asks(svc):
    topics = ["Cargo Temperature Control", "Boilers"]
    chunks = [chunk("Cargo Temperature Control"), chunk("Boilers", body="Boiler temperature must be monitored.")]
    clar = run(svc.maybe_clarify("temperature", chunks, topics))
    assert clar is not None and len([o for o in clar.options if o.kind == "topic"]) == 2


# ---- LLM grouping ----------------------------------------------------------
class FakeLLM:
    def __init__(self, payload=None, exc=None):
        self.payload, self.exc = payload, exc

    async def chat(self, messages, **kw):
        if self.exc:
            raise self.exc
        return self.payload if isinstance(self.payload, str) else json.dumps(self.payload)


def test_llm_grouping_used_when_valid():
    payload = {
        "ambiguous": True,
        "question": "Which kind of temperature do you mean?",
        "options": [
            {"label": "Cargo temperature", "hint": "keeping cargo safe", "topic_ids": [1],
             "query": "How is cargo temperature controlled on board?"},
            {"label": "Engine temperature", "hint": "", "topic_ids": [2],
             "query": "What are normal engine cooling water temperatures?"},
        ],
    }
    svc = ClarificationService(openai_service=FakeLLM(payload), use_llm=True)
    chunks = [chunk(n) for n in TOPICS[:3]]
    clar = run(svc.maybe_clarify("temperature", chunks, TOPICS))
    assert clar.question == "Which kind of temperature do you mean?"
    assert [o.label for o in clar.options[:2]] == ["Cargo temperature", "Engine temperature"]
    assert clar.options[0].topic_name == "Cargo Temperature Control"


def test_intro_comes_before_question_from_llm():
    payload = {
        "ambiguous": True,
        "intro": "Temperature is how hot or cold something is.",
        "question": "Which part of it do you want to dig into?",
        "options": [
            {"label": "Cargo temperature", "topic_ids": [1], "query": "How is cargo temperature controlled?"},
            {"label": "Engine temperature", "topic_ids": [2], "query": "What are normal engine temperatures?"},
        ],
    }
    svc = ClarificationService(openai_service=FakeLLM(payload), use_llm=True)
    clar = run(svc.maybe_clarify("temperature", [chunk(n) for n in TOPICS[:3]], TOPICS))
    assert clar.intro.startswith("Temperature is")
    text = clar.render_text()
    assert text.startswith("Temperature is how hot")
    assert text.index("Temperature is") < text.index("Which part")
    assert clar.to_dict()["intro"] == clar.intro


def test_quick_intro_fallback_when_grouping_has_none():
    class Seq:
        def __init__(self):
            self.n = 0
        async def chat(self, messages, **kw):
            self.n += 1
            if self.n == 1:
                return "not json"
            return "Temperature is a measure of how hot or cold something is."
    svc = ClarificationService(openai_service=Seq(), use_llm=True)
    clar = run(svc.maybe_clarify("temperature", [chunk(n) for n in TOPICS[:3]], TOPICS))
    assert clar is not None and clar.intro.startswith("Temperature is")
    assert clar.render_text().startswith(clar.intro)


def test_no_llm_means_no_intro(svc):
    clar = run(svc.maybe_clarify("temperature", [chunk(n) for n in TOPICS[:3]], TOPICS))
    assert clar.intro == ""


@pytest.mark.parametrize("bad", [
    FakeLLM(exc=RuntimeError("boom")),
    FakeLLM(payload="not json"),
    FakeLLM(payload={"ambiguous": False}),
    FakeLLM(payload={"ambiguous": True, "options": [{"label": "x", "topic_ids": [99], "query": "a b c d"}]}),
])
def test_llm_failures_fall_back_to_deterministic(bad):
    svc = ClarificationService(openai_service=bad, use_llm=True)
    clar = run(svc.maybe_clarify("temperature", [chunk(n) for n in TOPICS[:3]], TOPICS))
    assert clar is not None and clar.options[0].topic_name


def test_llm_timeout_falls_back():
    class Slow:
        async def chat(self, *a, **k):
            await asyncio.sleep(5)
    svc = ClarificationService(openai_service=Slow(), use_llm=True, llm_timeout=0.05)
    assert run(svc.maybe_clarify("temperature", [chunk(n) for n in TOPICS[:3]], TOPICS)) is not None


# ---- typed replies ---------------------------------------------------------
@pytest.fixture
def pending(svc):
    clar = run(svc.maybe_clarify("temperature", [chunk(n) for n in TOPICS[:3]], TOPICS))
    return clar.to_dict()


@pytest.mark.parametrize("reply,expected_label", [
    ("2", "Engine Cooling Water Temperature"),
    ("option 3", "Reefer Container Temperature Monitoring"),
    ("the second one", "Engine Cooling Water Temperature"),
    ("first", "Cargo Temperature Control"),
    ("cargo", "Cargo Temperature Control"),
    ("the reefer one", "Reefer Container Temperature Monitoring"),
    ("engine cooling", "Engine Cooling Water Temperature"),
    ("general", "General overview of temperature"),
    ("Cargo Temperature Control", "Cargo Temperature Control"),
])
def test_reply_resolution(svc, pending, reply, expected_label):
    opt = svc.resolve_reply(reply, pending)
    assert opt is not None and opt["label"] == expected_label


@pytest.mark.parametrize("reply", [
    "what is the boiling point of water", "temperature", "hello", "9", "water",  # 'water' hits two options? only one -> see below
])
def test_reply_that_is_a_new_question_is_not_hijacked(svc, pending, reply):
    if reply == "water":
        # exactly one option contains "water" (Engine Cooling Water Temperature) -> resolves, by design
        assert svc.resolve_reply(reply, pending)["label"] == "Engine Cooling Water Temperature"
    else:
        assert svc.resolve_reply(reply, pending) is None


def test_pending_only_when_last_message(svc, pending):
    msgs = [{"role": "user", "content": "temperature"}, {"role": "assistant", "content": "?", "clarification": pending}]
    assert svc.pending_from_messages(msgs) == pending
    assert svc.pending_from_messages(msgs + [{"role": "user", "content": "2"}]) is None


# ---- "General overview" option ---------------------------------------------
def test_general_option_query_round_trips(svc):
    clar = run(svc.maybe_clarify("temperature", [chunk(n) for n in TOPICS[:3]], TOPICS))
    general = next(o for o in clar.options if o.kind == "general")
    assert general.query.startswith(GENERAL_OVERVIEW_PREFIX)
    assert parse_general_overview(general.query) == "temperature"


@pytest.mark.parametrize("q,expected", [
    ("Give me a general overview of SMS", "SMS"),
    ("give me a general overview of cargo temperature?", "cargo temperature"),
    ("Give me a general overview of ", None),
    ("Tell me about Cargo Temperature Control", None),
])
def test_parse_general_overview(q, expected):
    assert parse_general_overview(q) == expected


def test_typed_general_resolves_to_general_option(svc):
    clar = run(svc.maybe_clarify("temperature", [chunk(n) for n in TOPICS[:3]], TOPICS)).to_dict()
    opt = svc.resolve_reply("general", clar)
    assert opt["kind"] == "general" and parse_general_overview(opt["query"]) == "temperature"


@pytest.mark.parametrize("q,expected", [
    ("what is temperature", True),
    ("What is temperature in few words?", True),
    ("temperature", True),
    ("define salinity", True),
    ("Give me a general overview of temperature", True),
    ("explain how to write a long cover letter for a job application at a big company", False),
    ("how do I repair the main engine turbocharger after a failure at sea", False),
])
def test_is_definitional_question(q, expected):
    assert is_definitional_question(q) is expected


@pytest.mark.parametrize("q,expected", [
    ("what is temperature in few words?", "temperature"),
    ("What is the Coriolis effect", "coriolis effect"),
    ("define salinity briefly", "salinity"),
    ("temperature", "temperature"),
])
def test_definitional_term(q, expected):
    assert definitional_term(q) == expected


def test_llm_dynamic_closing_in_render_text():
    custom_closing = "Tap any topic above to explore operating limits, or let me know the specific system you are working on today!"
    payload = {
        "ambiguous": True,
        "intro": "Temperature is how hot or cold something is.",
        "question": "Which part of it do you want to explore?",
        "closing": custom_closing,
        "options": [
            {"label": "Cargo temperature", "topic_ids": [1], "query": "How is cargo temperature controlled?"},
            {"label": "Engine temperature", "topic_ids": [2], "query": "What are normal engine temperatures?"},
        ],
    }
    svc = ClarificationService(openai_service=FakeLLM(payload), use_llm=True)
    clar = run(svc.maybe_clarify("temperature", [chunk(n) for n in TOPICS[:3]], TOPICS))
    assert clar.closing == custom_closing
    text = clar.render_text()
    assert text.endswith(custom_closing)
    assert "Tap one of the options, or just tell me what you're after" not in text


def test_fallback_dynamic_closing_not_hardcoded(svc):
    clar = run(svc.maybe_clarify("temperature", [chunk(n) for n in TOPICS[:3]], TOPICS))
    text = clar.render_text()
    # Ensure the old repetitive hardcoded line is completely gone
    assert "Tap one of the options, or just tell me what you're after and I'll find it." not in text
    # Ensure there is an interactive prompt at the end
    last_line = text.strip().split("\n")[-1]
    assert len(last_line) > 10
    assert any(w in last_line.lower() for w in ("tap", "select", "click", "choose", "pick", "options", "topics"))


def test_typo_autocorrection_in_fuzzy_service():
    from services.fuzzy_search_service import FuzzySearchService
    fuzzy = FuzzySearchService()
    fuzzy.database_topics = TOPICS
    
    # Test typos like 'teamprature' or 'teampareture'
    corrected_q, match = fuzzy.correct_query_typos("teamprature", TOPICS)
    assert match is not None
    assert match["misspelled_word"] == "teamprature"
    assert match["corrected_term"].lower() == "temperature"
    assert corrected_q.lower() == "temperature"

    # Test sentence containing typo
    sentence = "what is the normal teamprature of jacket water"
    corrected_sent, match_sent = fuzzy.correct_query_typos(sentence, TOPICS)
    assert match_sent is not None
    assert match_sent["misspelled_word"] == "teamprature"
    assert "temperature" in corrected_sent.lower()

