import pytest
from retrieval.bm25_store import BM25Store, tokenize


def test_bm25_tokenizer():
    text = "SOLAS Chapter II-2 Regulation 10: Fire fighting systems on Oil Tankers (COW & IG systems)"
    tokens = tokenize(text)
    assert "solas" in tokens
    assert "chapter" in tokens
    assert "regulation" in tokens
    assert "tankers" in tokens
    assert "cow" in tokens


def test_bm25_search_scoring():
    docs = [
        {
            "content_id": 1,
            "topic_name": "SOLAS Fire Safety Measures",
            "content": "Detailed procedures for fire detection, alarms, and firefighting appliances under SOLAS.",
        },
        {
            "content_id": 2,
            "topic_name": "Crude Oil Washing (COW) Operations",
            "content": "Guidelines on Crude Oil Washing (COW) procedures, inert gas requirements, and MARPOL Annex I compliance.",
        },
        {
            "content_id": 3,
            "topic_name": "STCW Watchkeeping Standards",
            "content": "Navigation watchkeeping rules, rest hours, and certification requirements for deck officers.",
        },
    ]

    bm25 = BM25Store()
    bm25.build_index(docs)

    assert bm25.corpus_size == 3
    assert bm25.is_indexed is True

    # Search for COW exact keyword
    cow_results = bm25.search("COW operations MARPOL", k=2)
    assert len(cow_results) > 0
    assert cow_results[0]["content_id"] == 2
    assert "Crude Oil Washing" in cow_results[0]["topic_name"]

    # Search for SOLAS exact keyword
    solas_results = bm25.search("SOLAS fire appliances", k=2)
    assert len(solas_results) > 0
    assert solas_results[0]["content_id"] == 1
