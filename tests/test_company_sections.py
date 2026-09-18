import asyncio
import pytest
from pipeline.company_query import company_query_node


class MockOpenAI:
    def __init__(self, answer_text: str):
        self.answer_text = answer_text

    async def chat(self, messages, **kwargs):
        return self.answer_text


def test_company_query_sections_split_and_uuids():
    answer = (
        "### 🏢 1. Demo Company's SMS\n"
        "**Document Title:** SMS Manual\n"
        "Company specific rules here.\n\n"
        "### 📘 2. Maritime Standards Benchmark\n"
        "General SOLAS guidelines here.\n\n"
        "### 🔍 3. Comparative Gap Analysis & AI Advisory Observations\n"
        "Gap analysis notes here.\n"
    )

    state = {
        "company_chunks": [
            {
                "topic_code": "uuid-company-chunk-111",
                "document_title": "Shipboard SMS Manual",
                "content": "SMS fire safety procedures and checks"
            }
        ],
        "retrieval_chunks": [
            {
                "topic_code": "uuid-course-chunk-222",
                "course_code": "course-uuid-alpha",
                "topic_name": "SOLAS Fire Safety",
                "content": "Course chunk 1"
            },
            {
                "topic_code": "uuid-course-chunk-333",
                "course_code": "course-uuid-beta",
                "topic_name": "SOLAS Inspection Regime",
                "content": "Course chunk 2"
            }
        ],
        "user_profile": {"company_name": "Demo Company"},
        "standalone_query": "What is SMS fire procedure?",
        "node_response": {}
    }

    result = asyncio.run(company_query_node(state, MockOpenAI(answer)))
    sections = result["node_response"]["sections"]

    assert len(sections) == 3
    assert sections[0]["topic_code"] == "uuid-company-chunk-111"
    assert sections[0]["topic_name"] == "Shipboard SMS Manual"
    assert "Company specific rules here." in sections[0]["content"]

    assert sections[1]["topic_code"] == "uuid-course-chunk-222"
    assert sections[1]["source_code"] == "course-uuid-alpha"
    assert sections[1]["course_code"] == "course-uuid-alpha"
    assert sections[1]["topic_name"] == "SOLAS Fire Safety"
    assert "General SOLAS guidelines here." in sections[1]["content"]

    assert sections[2]["topic_code"] == "uuid-course-chunk-333"
    assert sections[2]["source_code"] == "course-uuid-beta"
    assert sections[2]["course_code"] == "course-uuid-beta"
    assert sections[2]["topic_name"] == "SOLAS Inspection Regime"
    assert "Gap analysis notes here." in sections[2]["content"]


def test_company_sections_sse_streaming_emission():
    import json
    import re

    sections = [
        {"topic_code": "uuid-1", "topic_name": "Doc 1", "content": "Company procedure text"},
        {"topic_code": "uuid-2", "source_code": "course-1", "topic_name": "Topic 2", "content": "Maritime standard text"},
        {"topic_code": "uuid-3", "source_code": "course-2", "topic_name": "Topic 3", "content": "Gap analysis text"},
    ]

    emitted_source_topics = []
    for section in sections:
        source_data = {
            "type": "source_topic",
            "topic_code": section.get("topic_code"),
            "source_code": section.get("source_code") or section.get("course_code") or "",
            "topic_name": section.get("topic_name")
        }
        emitted_source_topics.append(source_data)

    assert len(emitted_source_topics) == 3
    assert emitted_source_topics[0] == {"type": "source_topic", "topic_code": "uuid-1", "source_code": "", "topic_name": "Doc 1"}
    assert emitted_source_topics[1] == {"type": "source_topic", "topic_code": "uuid-2", "source_code": "course-1", "topic_name": "Topic 2"}
    assert emitted_source_topics[2] == {"type": "source_topic", "topic_code": "uuid-3", "source_code": "course-2", "topic_name": "Topic 3"}

