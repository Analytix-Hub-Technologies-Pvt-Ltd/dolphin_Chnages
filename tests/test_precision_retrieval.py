# tests/test_precision_retrieval.py
from __future__ import annotations

import asyncio
import pytest
from typing import Any, Dict, List

from retrieval.normalization import (
    normalize_text_for_retrieval,
    tokenize_for_retrieval,
    match_phrase_flexible,
    simple_stem,
    extract_distinctive_terms,
)
from retrieval.bm25 import BM25Index
from retrieval.precision_scorer import (
    compute_chunk_precision_score,
    rank_and_filter_candidates,
)
from retrieval.faiss_store import FAISSStore


class MockVectorStore:
    def __init__(self, metadatas: List[Dict[str, Any]], vector_rankings: Dict[str, List[int]] = None):
        self.id_to_metadata = list(metadatas)
        self.vector_rankings = vector_rankings or {}
        self.bm25_index = BM25Index()
        self.bm25_index.build(self.id_to_metadata)
        self.is_loaded = True

    async def search_with_embeddings(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        # If predefined rankings for this query exist in test mock
        if query in self.vector_rankings:
            indices = self.vector_rankings[query]
            results = []
            for rank, idx in enumerate(indices[:k]):
                if 0 <= idx < len(self.id_to_metadata):
                    c = dict(self.id_to_metadata[idx])
                    c["_faiss_index"] = idx
                    c["_rank"] = rank
                    c["_score"] = 0.2 + (rank * 0.1)  # lower L2 distance for higher rank
                    results.append(c)
            return results

        # Default dummy vector search (returns top k in order)
        results = []
        for idx in range(min(k, len(self.id_to_metadata))):
            c = dict(self.id_to_metadata[idx])
            c["_faiss_index"] = idx
            c["_rank"] = idx
            c["_score"] = 0.3 + (idx * 0.1)
            results.append(c)
        return results

    def search_bm25(self, query: str, k: int = 30, filter_fn=None) -> List[Dict[str, Any]]:
        return self.bm25_index.search(query=query, top_k=k, filter_fn=filter_fn)

    async def search_hybrid(self, original_query: str, expanded_query: str = None, k: int = 10, filter_fn=None):
        from retrieval.faiss_store import FAISSStore
        # Re-use the real FAISSStore.search_hybrid logic
        return await FAISSStore.search_hybrid(
            self,
            original_query=original_query,
            expanded_query=expanded_query,
            k=k,
            filter_fn=filter_fn,
        )


# ---------------------------------------------------------------------------
# TEST SUITE
# ---------------------------------------------------------------------------

def test_normalization_variations():
    """Verify punctuation, apostrophes, dashes, and compound words normalize properly."""
    assert normalize_text_for_retrieval("snap-back' zone") == "snap back zone"
    assert normalize_text_for_retrieval("snap-back zone") == "snap back zone"
    assert normalize_text_for_retrieval("snap back zone") == "snap back zone"
    assert normalize_text_for_retrieval("Centrifugal Pumps:") == "centrifugal pumps"
    assert normalize_text_for_retrieval("Boiler   Safety—Valve") == "boiler safety valve"

    # Flexible matching
    assert match_phrase_flexible("snapback zone", "snap-back' zone") is True
    assert match_phrase_flexible("snap-back zone", "The snapback zone is hazardous") is True
    assert match_phrase_flexible("centrifugal pump", "Centrifugal Pumps and Systems") is True
    assert match_phrase_flexible("boiler safety valve", "Boiler Safety Valve Operation") is True


def test_distinctive_term_extraction():
    """Verify distinctive domain terms vs generic words."""
    terms1 = extract_distinctive_terms("centrifugal pumps")
    assert "centrifugal" in terms1
    assert "pumps" not in terms1  # generic word filtered

    terms2 = extract_distinctive_terms("What is the snapback zone during mooring operations?")
    assert "snapback" in terms2
    assert "mooring" in terms2
    assert "operations" not in terms2  # generic


def test_acceptance_criteria_test_a_centrifugal_pumps():
    """
    Test A: Query 'centrifugal pumps'
    Corpus has:
    - Topic A: 'Centrifugal Pumps' (specific)
    - Topic B: 'Cargo Pump Operation' (generic semantic match with pump keywords)
    FAISS mistakenly ranked Cargo Pump Operation higher in vector distance.
    Verify: Hybrid Precision Retrieval ranks 'Centrifugal Pumps' #1.
    """
    corpus = [
        {
            "content_id": 101,
            "topic_code": "TOPIC-CARGO-PUMP",
            "topic_name": "Cargo Pump Operation",
            "content": "Cargo pump starting, stopping, alarms, stripping, and discharge pressure monitoring procedures.",
        },
        {
            "content_id": 102,
            "topic_code": "TOPIC-CENTRIFUGAL-PUMP",
            "topic_name": "Centrifugal Pumps",
            "content": "Detailed operating principles of centrifugal pumps, impeller design, casing, NPSH, and priming.",
        },
        {
            "content_id": 103,
            "topic_code": "TOPIC-CENTRIFUGAL-PUMP",
            "topic_name": "Centrifugal Pumps",
            "content": "Centrifugal pump maintenance, cavitation prevention, and wear ring inspection.",
        },
    ]

    # Mock FAISS returning Cargo Pump Operation (idx 0) first, Centrifugal Pumps (idx 1, 2) second
    vector_rankings = {
        "centrifugal pumps": [0, 1, 2]
    }
    store = MockVectorStore(corpus, vector_rankings=vector_rankings)

    chunks, exact_topic, debug_info = asyncio.run(
        store.search_hybrid(original_query="centrifugal pumps", expanded_query="centrifugal pumps", k=5)
    )

    assert len(chunks) > 0
    assert chunks[0]["topic_name"] == "Centrifugal Pumps"
    assert exact_topic == "Centrifugal Pumps"

    # Context pollution prevention: Unrelated Cargo Pump Operation should NOT pollute exact topic focus
    selected_topic_names = [c["topic_name"] for c in chunks]
    assert "Cargo Pump Operation" not in selected_topic_names
    assert len(chunks) == 2  # Both chunks from Centrifugal Pumps family retained!


def test_singular_plural_matching():
    """Query 'centrifugal pump' (singular) should retrieve topic 'Centrifugal Pumps' (plural)."""
    corpus = [
        {
            "content_id": 201,
            "topic_code": "TOPIC-PUMPS-GEN",
            "topic_name": "General Pump Operation",
            "content": "General introduction to pumps on vessels.",
        },
        {
            "content_id": 202,
            "topic_code": "TOPIC-CENTRIFUGAL",
            "topic_name": "Centrifugal Pumps",
            "content": "Centrifugal pump working principles and flow characteristics.",
        }
    ]
    store = MockVectorStore(corpus, vector_rankings={"centrifugal pump": [0, 1]})

    chunks, exact_topic, debug_info = asyncio.run(
        store.search_hybrid(original_query="centrifugal pump", expanded_query="centrifugal pump", k=5)
    )

    assert chunks[0]["topic_name"] == "Centrifugal Pumps"
    assert exact_topic == "Centrifugal Pumps"


def test_acceptance_criteria_test_b_snapback_variations():
    """
    Test B: Document contains "snap-back' zone".
    User asks: "Explain snapback zone" or "What is the snapback zone during mooring operations?"
    Verify: The document chunk is retrieved and ranked #1.
    """
    corpus = [
        {
            "content_id": 301,
            "topic_code": "TOPIC-MOORING-GEN",
            "topic_name": "Mooring Operations Overview",
            "content": "General mooring deck layout and team communication.",
        },
        {
            "content_id": 302,
            "topic_code": "TOPIC-SNAPBACK",
            "topic_name": "Mooring Safety - Snap-back' Zone",
            "content": "A snap-back' zone is the dangerous area where a parted synthetic mooring line recoils violently.",
        }
    ]
    store = MockVectorStore(corpus, vector_rankings={"Explain snapback zone": [0, 1]})

    # Test 1: "snapback zone"
    chunks1, exact1, _ = asyncio.run(
        store.search_hybrid(original_query="snapback zone", expanded_query="Explain snapback zone", k=5)
    )
    assert chunks1[0]["content_id"] == 302

    # Test 2: "What is the snapback zone during mooring operations?"
    chunks2, exact2, _ = asyncio.run(
        store.search_hybrid(
            original_query="What is the snapback zone during mooring operations?",
            expanded_query="mooring line snapback zone safety precautions",
            k=5
        )
    )
    assert chunks2[0]["content_id"] == 302


def test_cargo_pump_operation_exact():
    """Query 'cargo pump operation' must retrieve 'Cargo Pump Operation'."""
    corpus = [
        {
            "content_id": 401,
            "topic_code": "TOPIC-CENTRIFUGAL",
            "topic_name": "Centrifugal Pumps",
            "content": "Impellers and casing details.",
        },
        {
            "content_id": 402,
            "topic_code": "TOPIC-CARGO-PUMP",
            "topic_name": "Cargo Pump Operation",
            "content": "Starting procedures, stripping, discharge pressure.",
        }
    ]
    store = MockVectorStore(corpus, vector_rankings={"cargo pump operation": [0, 1]})

    chunks, exact_topic, _ = asyncio.run(
        store.search_hybrid(original_query="cargo pump operation", expanded_query="cargo pump operation", k=5)
    )
    assert chunks[0]["topic_name"] == "Cargo Pump Operation"


def test_emergency_fire_pump_and_boiler_safety_valve():
    """Test queries with multiple distinctive technical terms."""
    corpus = [
        {
            "content_id": 501,
            "topic_code": "TOPIC-FIRE",
            "topic_name": "Emergency Fire Pump",
            "content": "Emergency fire pump location, power source, and priming requirements.",
        },
        {
            "content_id": 502,
            "topic_code": "TOPIC-BOILER",
            "topic_name": "Boiler Safety Valve",
            "content": "Testing and easing gear of boiler safety valves as per SOLAS regulations.",
        },
        {
            "content_id": 503,
            "topic_code": "TOPIC-GEN-BOILER",
            "topic_name": "Boiler Operation Overview",
            "content": "General steam generation and feed water.",
        }
    ]
    store = MockVectorStore(corpus)

    # Test emergency fire pump
    chunks_fire, _, _ = asyncio.run(
        store.search_hybrid(original_query="emergency fire pump", expanded_query="emergency fire pump", k=5)
    )
    assert chunks_fire[0]["topic_name"] == "Emergency Fire Pump"

    # Test boiler safety valve
    chunks_boiler, _, _ = asyncio.run(
        store.search_hybrid(original_query="boiler safety valve", expanded_query="boiler safety valve", k=5)
    )
    assert chunks_boiler[0]["topic_name"] == "Boiler Safety Valve"


def test_acceptance_criteria_test_d_company_isolation():
    """Test D: Company query must never leak other company's data."""
    corpus = [
        {
            "content_id": 601,
            "company_id": "COMP-A",
            "company_name": "Alpha Shipping",
            "document_title": "Shipboard SMS Manual Alpha.docx",
            "content": "Alpha enclosed space entry checklist and gas detection.",
        },
        {
            "content_id": 602,
            "company_id": "COMP-B",
            "company_name": "Beta Marine",
            "document_title": "Shipboard SMS Manual Beta.docx",
            "content": "Beta confidential enclosed space entry and hot work procedures.",
        }
    ]

    # Filter function representing user from COMP-A
    def filter_comp_a(chunk):
        return chunk.get("company_id") == "COMP-A"

    store = MockVectorStore(corpus)
    chunks, _, _ = asyncio.run(
        store.search_hybrid(
            original_query="enclosed space entry",
            expanded_query="enclosed space entry",
            filter_fn=filter_comp_a,
            k=5,
        )
    )

    for c in chunks:
        assert c["company_id"] == "COMP-A"
        assert c["company_id"] != "COMP-B"


def test_acceptance_criteria_test_e_bm25_fallback():
    """Test E: If BM25 is disabled or fails, application operates gracefully using FAISS."""
    corpus = [
        {
            "content_id": 701,
            "topic_name": "Anchor Watch Procedures",
            "content": "Checking GPS position, drift, radar guard zones.",
        }
    ]
    store = MockVectorStore(corpus)
    # Simulate BM25 disabled/None
    store.bm25_index = None

    chunks, _, _ = asyncio.run(
        store.search_hybrid(original_query="anchor watch", expanded_query="anchor watch", k=5)
    )
    assert len(chunks) == 1
    assert chunks[0]["topic_name"] == "Anchor Watch Procedures"


def test_acceptance_criteria_test_f_irrelevant_faiss_recovery():
    """
    Test F: When FAISS returns irrelevant results with non-zero scores,
    BM25/lexical precision recovers the correct topic.
    """
    corpus = [
        {
            "content_id": 801,
            "topic_name": "Steering Gear Maintenance",
            "content": "Hydraulic rams and rudder angle indicators.",
        },
        {
            "content_id": 802,
            "topic_name": "Oily Water Separator 15ppm Monitor",
            "content": "Calibration and cleaning of OWS 15 ppm bilge alarm sensor.",
        }
    ]
    # FAISS erroneously returns steering gear (idx 0)
    vector_rankings = {
        "15ppm monitor": [0]
    }
    store = MockVectorStore(corpus, vector_rankings=vector_rankings)

    chunks, exact_topic, _ = asyncio.run(
        store.search_hybrid(original_query="15ppm monitor", expanded_query="15ppm monitor", k=5)
    )
    assert chunks[0]["content_id"] == 802
    assert "Oily Water Separator" in chunks[0]["topic_name"]


def test_scope_check_snapback():
    """Verify that 'explain snap back zone' is recognized as in-scope maritime query."""
    from services.chat_service import ChatService
    chat_svc = ChatService(None, None, None, None)
    scope = asyncio.run(chat_svc.check_query_scope("explain snap back zone", []))
    assert scope == "IN-SCOPE"


def test_company_retrieval_centrifugal_pumps_pruning():
    """
    Verify that for company retrieval with query 'centrifugal pumps',
    generic 'Cargo Pump Operation' chunks are pruned and only 'Maintenance Procedure for Pumps (Centrifugal)'
    is retrieved and prioritized in company_chunks.
    """
    from pipeline.company_retrieval import company_retrieval_node

    class MockCompanyStore:
        def __init__(self):
            self.id_to_metadata = [
                {
                    "document_id": "doc1",
                    "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx",
                    "company_id": "824866",
                    "company_name": "CMS Demo Company",
                    "chunk_index": 0,
                    "content": "SOP Name: Cargo Pump Operation\nSection: III.5.2.3.7 Cargo Pump Operation\nCargo Pump Operation Prior to Every Discharge Operation",
                },
                {
                    "document_id": "doc1",
                    "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx",
                    "company_id": "824866",
                    "company_name": "CMS Demo Company",
                    "chunk_index": 1,
                    "content": "Starting the Pump\nLine Setup: Set the line as per cargo plan\nSlow Speed Start: Start pump in slow speed mode",
                },
                {
                    "document_id": "doc1",
                    "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx",
                    "company_id": "824866",
                    "company_name": "CMS Demo Company",
                    "chunk_index": 50,
                    "content": "III.7.21.3 Maintenance Procedure for Pumps\nMaintenance of various salt water and fresh water centrifugal pumps shall be done as per the guidelines given in section III.7.17. Given below is the checklist for pump maintenance:",
                },
                {
                    "document_id": "doc1",
                    "document_title": "Shipboard SMS Manual (Chemical)-Completed (1).docx",
                    "company_id": "824866",
                    "company_name": "CMS Demo Company",
                    "chunk_index": 51,
                    "content": "During Maintenance\nAll tally marks put to see parts are assembled properly\nCheck trueness of the shaft and condition of bearings and seals",
                },
            ]

        async def search_with_embeddings(self, query, k=250):
            # Simulate FAISS returning both cargo pump and centrifugal pump
            res = []
            for idx, m in enumerate(self.id_to_metadata):
                c = dict(m)
                c["_faiss_index"] = idx
                c["_score"] = 0.5
                res.append(c)
            return res

        def search_bm25(self, query, k=50, filter_fn=None):
            # BM25 returns centrifugal pump chunk #50 with high score
            c = dict(self.id_to_metadata[2])
            c["_faiss_index"] = 2
            c["_bm25_score"] = 5.0
            return [c]

    store = MockCompanyStore()
    state = {
        "user_profile": {
            "company_id": "824866",
            "company_name": "CMS Demo Company",
            "ship_type": "Chemical Tanker",
        },
        "current_query": "centrifugal pumps",
        "standalone_query": "centrifugal pumps",
    }

    updated_state = asyncio.run(company_retrieval_node(state, store))
    chunks = updated_state.get("company_chunks", [])
    assert len(chunks) > 0

    # Ensure all retrieved chunks belong to the centrifugal pumps section and NOT Cargo Pump Operation
    for c in chunks:
        assert "Cargo Pump Operation" not in c["content"]
        assert c["chunk_index"] in (50, 51) or "centrifugal" in c["content"].lower() or "III.7.21.3" in c["content"]

    assert any("centrifugal pumps" in c["content"] for c in chunks)


