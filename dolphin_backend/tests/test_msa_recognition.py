import pytest
from services.maritime_acronyms import (
    find_acronyms_in_query,
    get_acronym_expansion,
    is_known_maritime_acronym,
    has_conflicting_acronym,
    GLOBAL_MARITIME_FRAMEWORKS,
)
from services.off_topic_detector import (
    is_off_topic_query,
    is_marine_domain_query,
    has_strong_marine_signal,
)


def test_msa_acronym_recognition():
    query = "what are the main changes made in msa 2025"
    acrs = find_acronyms_in_query(query)
    assert "MSA" in acrs, f"Expected MSA to be detected in '{query}', got {acrs}"
    assert is_known_maritime_acronym("MSA") is True
    
    expansions = get_acronym_expansion("MSA")
    assert any("merchant shipping act" in exp for exp in expansions)
    assert any("maritime safety administration" in exp for exp in expansions)


def test_msa_domain_detection():
    query = "what are the main changes made in msa 2025"
    assert is_off_topic_query(query) is False
    assert is_marine_domain_query(query) is True
    assert has_strong_marine_signal(query) is True


def test_msa_global_framework_no_conflict():
    assert "MSA" in GLOBAL_MARITIME_FRAMEWORKS
    query = "what are the main changes made in msa 2025"
    # Even if candidate mentions SOLAS or MARPOL, it shouldn't conflict
    assert has_conflicting_acronym(query, "SOLAS amendments 2024") is False
    assert has_conflicting_acronym(query, "MARPOL Annex VI") is False


def test_msa_query_analyzer_intent():
    import asyncio
    from services.query_analyzer import QueryAnalyzer
    
    class DummyIntentService:
        async def classify_intent(self, q):
            return "OFF_TOPIC"  # Even if external LLM mistakenly returns OFF_TOPIC
            
    analyzer = QueryAnalyzer(DummyIntentService())
    standalone, category, _ = asyncio.run(
        analyzer.analyze_query("what are the main changes made in msa 2025", [])
    )
    # Should be overridden to QUERY because msa / merchant shipping is a prioritized marine term
    assert category == "QUERY", f"Expected QUERY category, got {category}"
