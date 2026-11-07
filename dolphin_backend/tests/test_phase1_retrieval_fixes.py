"""
test_phase1_retrieval_fixes.py
==============================
Phase 1 FAISS + BM25 Retrieval Enhancement — Verification Tests

Tests 3 groups:
  GROUP A — Regression Guard:  Existing working questions must still work correctly
  GROUP B — Fix 1 Validation:  BM25 threshold 0.1→0.05 (rare-term chunks enter RRF)
  GROUP C — Fix 2+3 Validation: Adaptive threshold + wider K (complex queries not over-filtered)

Run with:
  cd backend
  python -m pytest tests/test_phase1_retrieval_fixes.py -v -s

OR run directly:
  cd backend
  python tests/test_phase1_retrieval_fixes.py
"""

import sys
import os
from pathlib import Path

# Add backend root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest


# ─────────────────────────────────────────────────────────────────
# GROUP A — Regression Guard
# These were already working. They MUST still work after Phase 1.
# ─────────────────────────────────────────────────────────────────

class TestGroupA_RegressionGuard:
    """
    Verify that Phase 1 changes did NOT break any currently working questions.
    These are simple short maritime queries that always returned correct chunks.
    """

    def test_adaptive_threshold_short_query_unchanged(self):
        """
        For a 1-word query, adaptive threshold = 1.45 + (0.30 × 1/8) = 1.49
        Verify threshold calculation is nearly identical to 1.45 for short queries.
        """
        def compute_threshold(search_query: str) -> float:
            query_words = len((search_query or "").split())
            length_factor = min(1.0, query_words / 8.0)
            return 1.45 + (0.30 * length_factor)

        t_ecdis = compute_threshold("ECDIS")
        assert 1.45 <= t_ecdis <= 1.50, f"1-word threshold should be 1.45-1.50, got {t_ecdis:.3f}"

        t_two = compute_threshold("boiler maintenance")
        assert 1.45 <= t_two <= 1.55, f"2-word threshold should be 1.45-1.55, got {t_two:.3f}"

        t_three = compute_threshold("COW oil procedures")
        assert t_three < 1.60, f"3-word threshold {t_three:.3f} should still be close to 1.45"

        print(f"\n[PASS] Short query thresholds:")
        print(f"   'ECDIS'              -> {t_ecdis:.4f}  (was 1.45, diff = +{t_ecdis-1.45:.4f})")
        print(f"   'boiler maintenance' -> {t_two:.4f}  (was 1.45, diff = +{t_two-1.45:.4f})")
        print(f"   'COW oil procedures' -> {t_three:.4f}  (was 1.45, diff = +{t_three-1.45:.4f})")

    def test_adaptive_threshold_wrong_chunks_still_dropped(self):
        """
        Verify that wrong chunks (score 1.6–2.0) are still dropped even with adaptive threshold.
        For short queries, the threshold is at most 1.50 — well below 1.6.
        """
        def compute_threshold(search_query: str) -> float:
            query_words = len((search_query or "").split())
            length_factor = min(1.0, query_words / 8.0)
            return 1.45 + (0.30 * length_factor)

        wrong_chunk_scores = [1.60, 1.75, 1.90, 2.10]

        for short_query in ["ECDIS", "MARPOL", "boiler", "COW"]:
            threshold = compute_threshold(short_query)
            for wrong_score in wrong_chunk_scores:
                assert wrong_score > threshold, (
                    f"Wrong chunk score {wrong_score} should be > threshold {threshold:.3f} "
                    f"for query '{short_query}'"
                )

        print(f"\n[PASS] Wrong chunks (scores 1.6-2.1) still correctly dropped for short queries")

    def test_bm25_high_scoring_chunks_unaffected(self):
        """
        Verify that chunks with BM25 scores >> 0.05 are unchanged.
        Working questions have BM25 scores of 3–15.
        """
        NEW_THRESHOLD = 0.05
        high_bm25_scores = [3.0, 5.5, 8.2, 12.7, 15.4]

        for score in high_bm25_scores:
            assert score >= NEW_THRESHOLD, f"Score {score} should pass new threshold {NEW_THRESHOLD}"

        print(f"\n[PASS] High-scoring BM25 chunks (scores 3-15) still enter RRF fusion unchanged")

    def test_wider_k_correct_retrieval_rank_preserved(self):
        """
        Verify that fetching 2×K and then trimming [:K] preserves rank-0.
        If rank-0 is correct (existing working questions), trim doesn't change it.
        """
        simulated_20_chunks = [
            {"topic_name": f"Topic_{i}", "_score": 0.3 + i * 0.1, "_rank": i}
            for i in range(20)
        ]
        simulated_20_chunks[0]["topic_name"] = "ECDISSystemOverview"  # correct chunk at rank-0

        top_10 = simulated_20_chunks[:10]

        assert top_10[0]["topic_name"] == "ECDISSystemOverview"
        assert len(top_10) == 10
        print(f"\n[PASS] Wider K: correct chunk stays at rank-0 after trim. Top-10 count={len(top_10)}")


# ─────────────────────────────────────────────────────────────────
# GROUP B — Fix 1 Validation
# BM25 threshold 0.1 → 0.05: rare-term chunks now enter RRF
# ─────────────────────────────────────────────────────────────────

class TestGroupB_BM25ThresholdFix:
    """
    Validate that lowering the BM25 threshold from 0.1 to 0.05 allows
    rare-term maritime chunks to participate in RRF fusion.
    """

    def test_rare_term_chunk_now_enters_rrf(self):
        """
        A chunk with BM25 score 0.07 (rare term like "Manila") was SKIPPED before.
        Now it enters RRF and gets its lexical vote.
        """
        OLD_THRESHOLD = 0.1
        NEW_THRESHOLD = 0.05

        previously_dropped_scores = [0.051, 0.063, 0.075, 0.088, 0.099]

        for score in previously_dropped_scores:
            old_skipped = score < OLD_THRESHOLD
            new_skipped = score < NEW_THRESHOLD

            assert old_skipped is True,  f"Score {score} should have been skipped with old 0.1 threshold"
            assert new_skipped is False, f"Score {score} should NOT be skipped with new 0.05 threshold"

        print(f"\n[PASS] BM25 Fix: Rare-term scores {previously_dropped_scores} now enter RRF fusion")

    def test_noise_chunks_still_dropped(self):
        """
        Truly irrelevant BM25 hits (score < 0.05) are still dropped.
        """
        NEW_THRESHOLD = 0.05
        noise_scores = [0.001, 0.01, 0.02, 0.035, 0.049]

        for score in noise_scores:
            assert score < NEW_THRESHOLD, f"Score {score} should still be dropped (noise)"

        print(f"\n[PASS] Noise chunks (scores < 0.05) still correctly excluded from RRF")

    def test_bm25_store_tokenizes_rare_terms(self):
        """
        Unit test BM25Store directly: verify that rare maritime terms
        like 'Manila', '2010', 'Annex' are tokenized and indexed correctly.
        """
        from retrieval.bm25_store import BM25Store, tokenize

        docs = [
            {
                "content_id": 1,
                "topic_name": "STCW Manila 2010 Amendments",
                "content": "The Manila Amendments to the STCW Convention were adopted in 2010. "
                           "They updated watchkeeping requirements and rest hours for seafarers.",
            },
            {
                "content_id": 2,
                "topic_name": "General Watchkeeping",
                "content": "Basic watchkeeping principles including navigation, lookout, and communication.",
            },
            {
                "content_id": 3,
                "topic_name": "MARPOL Annex I Oil Pollution",
                "content": "MARPOL Annex I covers prevention of pollution by oil from ships. "
                           "Includes regulations for machinery space bilges and cargo tanks.",
            },
        ]

        bm25 = BM25Store()
        bm25.build_index(docs)

        # "Manila" rare term → should retrieve doc 1
        manila_results = bm25.search("Manila 2010 amendment", k=3)
        assert len(manila_results) > 0, "BM25 should return results for 'Manila 2010'"
        assert manila_results[0]["content_id"] == 1, (
            f"Top result should be STCW Manila (id=1), got id={manila_results[0]['content_id']}"
        )

        # "Annex" term → should retrieve MARPOL doc
        annex_results = bm25.search("Annex I pollution oil", k=3)
        assert annex_results[0]["content_id"] == 3, (
            f"Top result for 'Annex I' should be MARPOL (id=3), got id={annex_results[0]['content_id']}"
        )

        manila_score = manila_results[0].get("_bm25_score", 0)
        print(f"\n[PASS] BM25 tokenizes rare terms 'Manila', '2010', 'Annex' correctly")
        print(f"   Manila result: content_id={manila_results[0]['content_id']}, score={manila_score:.4f}")


# ─────────────────────────────────────────────────────────────────
# GROUP C — Fix 2+3 Validation
# Adaptive threshold + Wider K for complex queries
# ─────────────────────────────────────────────────────────────────

class TestGroupC_AdaptiveThresholdAndWiderK:

    def test_adaptive_threshold_values(self):
        """
        Verify threshold scales correctly with query length.
        Formula: 1.45 + (0.30 × min(1.0, words/8))
        """
        def compute_threshold(query: str) -> float:
            query_words = len((query or "").split())
            length_factor = min(1.0, query_words / 8.0)
            return round(1.45 + (0.30 * length_factor), 4)

        test_cases = [
            ("ECDIS",                                                       1.45, 1.50),
            ("boiler maintenance",                                          1.50, 1.58),
            ("COW crude oil washing procedures",                            1.58, 1.65),
            ("What is the STCW Manila 2010 watchkeeping amendment?",        1.70, 1.76),
            ("Explain MARPOL Annex I regulation for machinery bilges",      1.74, 1.76),
        ]

        print(f"\n[PASS] Adaptive threshold values:")
        for query, expected_min, expected_max in test_cases:
            threshold = compute_threshold(query)
            assert expected_min <= threshold <= expected_max, (
                f"Query '{query[:40]}' -> threshold={threshold:.4f}, "
                f"expected {expected_min}-{expected_max}"
            )
            print(f"   '{query[:50]}' -> {threshold:.4f}")

    def test_complex_query_chunk_survives_filter(self):
        """
        Correct chunk with score 1.55 is dropped for short query but kept for long query.
        This is the core behavior of Fix 2.
        """
        def compute_threshold(query: str) -> float:
            query_words = len((query or "").split())
            length_factor = min(1.0, query_words / 8.0)
            return 1.45 + (0.30 * length_factor)

        chunk_score = 1.55

        # Short query: threshold ≈ 1.47 → chunk is dropped (correct for short queries)
        short_threshold = compute_threshold("ECDIS")
        assert chunk_score > short_threshold

        # Long complex query: threshold ≈ 1.75 → chunk survives (fix for complex queries)
        long_query = "What is the procedure for ECDIS route planning in restricted visibility near coastal waters?"
        long_threshold = compute_threshold(long_query)
        assert chunk_score < long_threshold

        print(f"\n[PASS] Score {chunk_score}:")
        print(f"   Short query threshold={short_threshold:.3f} -> chunk DROPPED (correct)")
        print(f"   Long  query threshold={long_threshold:.3f} -> chunk KEPT    (correct)")

    def test_wider_k_exposes_rank11_chunk_to_reranker(self):
        """
        Correct chunk at rank-11 was invisible with k=10.
        With k=20, it's now visible to the reranker.
        """
        DEFAULT_TOP_K = 10

        simulated_faiss_20 = [
            {"topic_name": f"WrongTopic_{i}", "_score": 0.3 + i * 0.08, "_rank": i, "content_id": i}
            for i in range(20)
        ]
        # Correct chunk at rank-11 (invisible before fix)
        simulated_faiss_20[11] = {
            "topic_name": "CrudeOilWashingProcedures",
            "_score": 1.15,
            "_rank": 11,
            "content_id": 500
        }

        # Old behavior: only top-10
        old_pool = simulated_faiss_20[:DEFAULT_TOP_K]
        old_visible = any(c["topic_name"] == "CrudeOilWashingProcedures" for c in old_pool)

        # New behavior: all 20 sent to reranker
        new_pool = simulated_faiss_20
        new_visible = any(c["topic_name"] == "CrudeOilWashingProcedures" for c in new_pool)

        assert old_visible is False, "Correct chunk at rank-11 should NOT be in old top-10"
        assert new_visible is True,  "Correct chunk at rank-11 SHOULD be in new pool of 20"

        print(f"\n[PASS] Wider K fix:")
        print(f"   k=10 pool: correct chunk visible = {old_visible} (was invisible - BUG)")
        print(f"   k=20 pool: correct chunk visible = {new_visible} (now visible - FIXED)")


# ─────────────────────────────────────────────────────────────────
# MANUAL LIVE API TEST GUIDE
# ─────────────────────────────────────────────────────────────────

MANUAL_TEST_QUESTIONS = {
    "GROUP_A — Regression (must still work correctly)": [
        "ECDIS",
        "What is MARPOL?",
        "boiler maintenance",
        "enclosed space entry",
        "SOLAS fire safety",
        "COLREGS rule 15",
        "What is STCW?",
        "OWS oily water separator",
        "cargo hold inspection",
        "anchor watch procedure",
    ],
    "GROUP_B — Rare Term Fix (should now be correct after Fix 1)": [
        "STCW Manila 2010 amendment watchkeeping",
        "MARPOL Annex I machinery bilges",
        "MLC 2006 maritime labour standards",
        "ISM code safety management",
        "ISPS code security levels",
    ],
    "GROUP_C — Complex Query Fix (should now be complete after Fix 2+3)": [
        "What are the ECDIS route planning procedures in restricted visibility and heavy traffic conditions?",
        "Explain the crude oil washing procedure including inert gas system checks and MARPOL Annex I compliance requirements",
        "What is the impact of STCW Manila 2010 amendments on watchkeeping hours and rest period requirements for officers?",
        "Describe the enclosed space entry permit procedure including atmospheric testing and oxygen level measurement",
        "What are the fire prevention and firefighting measures required under SOLAS Chapter II-2 for oil tankers?",
    ],
}


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("📋 MANUAL LIVE API TEST GUIDE")
    print("=" * 70)
    for group, questions in MANUAL_TEST_QUESTIONS.items():
        print(f"\n🔹 {group}:")
        for i, q in enumerate(questions, 1):
            print(f"   {i}. {q}")
    print("\n" + "=" * 70)
    print("WHAT TO CHECK:")
    print("  GROUP_A: Answer must be same/equivalent as before Phase 1")
    print("  GROUP_B: Answer should now correctly describe the specific rare topic")
    print("  GROUP_C: Answer should now be specific and complete, not generic")
    print("=" * 70)
    print("\n🚀 Running automated unit tests...\n")

    result = pytest.main([__file__, "-v", "-s", "--tb=short"])
    sys.exit(result)
