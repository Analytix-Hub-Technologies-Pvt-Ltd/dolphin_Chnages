import asyncio
import pytest
from pipeline.retrieval import retrieval_node

def test_broad_acronym_boosts_overview_chunk():
    async def _test():
        mock_chunks = [
            {"topic_code": "02", "topic_name": "EGCS Scheme B Continuous Monitoring", "topic_content": "Scheme B details...", "content": "Scheme B"},
            {"topic_code": "03", "topic_name": "EGCS Washwater Discharge Criteria", "topic_content": "Washwater pH limits...", "content": "Washwater"},
            {"topic_code": "01", "topic_name": "Overview of Exhaust Gas Cleaning Systems (EGCS)", "topic_content": "Introduction to EGCS...", "content": "Overview"}
        ]
        class MockVectorStore:
            async def search_with_embeddings(self, q, k):
                return list(mock_chunks)

        state_new = {
            "current_query": "EGCS",
            "router_decision": {"node_type": "query", "standalone_query": "EGCS"},
            "_sme_checked": True
        }
        res = await retrieval_node(state_new, MockVectorStore())
        chunks = res["retrieval_chunks"]
        assert len(chunks) == 3
        # The overview chunk must be boosted to rank 0!
        assert chunks[0]["topic_name"] == "Overview of Exhaust Gas Cleaning Systems (EGCS)"
        assert chunks[0]["_rank"] == 0

    asyncio.run(_test())

def test_specific_procedural_query_does_not_force_overview():
    async def _test():
        mock_chunks = [
            {"topic_code": "03", "topic_name": "EGCS Washwater Discharge Criteria", "topic_content": "Washwater pH limits and sensors...", "content": "Washwater"},
            {"topic_code": "01", "topic_name": "Overview of Exhaust Gas Cleaning Systems (EGCS)", "topic_content": "Introduction to EGCS...", "content": "Overview"}
        ]
        class MockVectorStore:
            async def search_with_embeddings(self, q, k):
                return list(mock_chunks)

        state_new = {
            "current_query": "What is the pH limit for EGCS washwater discharge?",
            "router_decision": {"node_type": "query", "standalone_query": "What is the pH limit for EGCS washwater discharge?"},
            "_sme_checked": True
        }
        res = await retrieval_node(state_new, MockVectorStore())
        chunks = res["retrieval_chunks"]
        # For a specific question about washwater pH limits, it should NOT boost the overview chunk over the specific chunk
        assert chunks[0]["topic_name"] == "EGCS Washwater Discharge Criteria"

    asyncio.run(_test())


def test_topic_overview_classified_as_query():
    from services.query_analyzer import EnhancedQueryAnalyzer

    analyzer = EnhancedQueryAnalyzer(None)
    queries = [
        "Overview of ECDIS",
        "Overview of EGCS",
        "Summary of SOLAS",
        "give me an overview of boiler safety valves",
    ]
    for q in queries:
        res = asyncio.run(analyzer.classify_for_router(q, []))
        assert res["node_type"] == "query", f"Expected 'query' for '{q}', got {res['node_type']}"
        assert res["category"] == "QUERY", f"Expected 'QUERY' for '{q}', got {res['category']}"


def test_session_summary_classified_as_summary():
    from services.query_analyzer import EnhancedQueryAnalyzer

    analyzer = EnhancedQueryAnalyzer(None)
    queries = [
        "summarize our session so far",
        "give me a summary of my learnings",
        "recap",
        "summarize what we discussed",
    ]
    for q in queries:
        res = asyncio.run(analyzer.classify_for_router(q, []))
        assert res["node_type"] == "summary", f"Expected 'summary' for '{q}', got {res['node_type']}"
        assert res["category"] == "SUMMARY", f"Expected 'SUMMARY' for '{q}', got {res['category']}"

