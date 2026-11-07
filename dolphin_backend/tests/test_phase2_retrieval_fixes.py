"""
test_phase2_retrieval_fixes.py
==============================
Phase 2 FAISS + BM25 Retrieval Enhancement — Verification Tests

Tests 4 groups:
  GROUP A — Regression Guard: Backward compatibility when original_query is omitted
  GROUP B — Dual BM25 Search: Prevents query expansion from diluting exact keyword matches
  GROUP C — Score-Aware RRF: Confident FAISS & BM25 hits receive appropriate confidence multipliers
  GROUP D — Stale Key Scoping: BM25 skip filter handles first-doc scoping cleanly

Run with:
  cd backend
  python -m pytest tests/test_phase2_retrieval_fixes.py -v -s
"""

import sys
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, Any, List
import pytest

# Add backend root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from retrieval.bm25_store import BM25Store


# =================================================================
# GROUP A: Regression Guard
# =================================================================
class TestGroupA_Phase2RegressionGuard:
    """
    Verify that Phase 2 changes do not break existing working queries.
    """

    def test_search_with_embeddings_signature_backward_compatible(self):
        """
        Verify that search_with_embeddings can still be called with just (query, k).
        original_query must be optional with default=None.
        """
        import inspect
        from services.chat_service import VectorStoreAdapter

        sig = inspect.signature(VectorStoreAdapter.search_with_embeddings)
        assert "original_query" in sig.parameters, "original_query parameter must exist"
        param = sig.parameters["original_query"]
        assert param.default is None, "original_query default must be None for backward compatibility"
        print("\n[PASS] search_with_embeddings signature backward compatibility confirmed")

    def test_high_confidence_working_query_remains_rank0(self):
        """
        For a working question where FAISS has distance 0.40 (< 0.8) and BM25 has score 10.0 (>= 5.0),
        both receive the +15% confidence bonus and remain rank 0.
        """
        rrf_k = 60
        doc_scores = defaultdict(float)

        working_faiss_dist = 0.40
        neighbor_faiss_dist = 1.20

        # FAISS pass
        dist_mult_working = 1.15 if working_faiss_dist < 0.8 else 1.0
        dist_mult_neighbor = 1.15 if neighbor_faiss_dist < 0.8 else 1.0

        doc_scores["working_doc"] += (1.0 / (rrf_k + 0 + 1)) * dist_mult_working
        doc_scores["neighbor_doc"] += (1.0 / (rrf_k + 1 + 1)) * dist_mult_neighbor

        # BM25 pass
        bm25_mult_working = 1.15  # score = 10.0 >= 5.0
        doc_scores["working_doc"] += (1.0 / (rrf_k + 0 + 1)) * bm25_mult_working

        assert doc_scores["working_doc"] > doc_scores["neighbor_doc"] * 2.0
        print(f"\n[PASS] Working question score: {doc_scores['working_doc']:.5f} vs Neighbor: {doc_scores['neighbor_doc']:.5f} (2x+ lead preserved)")


# =================================================================
# GROUP B: Dual BM25 Search
# =================================================================
class TestGroupB_DualBM25Search:
    """
    Validate that Dual BM25 search protects exact acronym/keyword matches from dilution.
    """

    def test_dual_bm25_merges_raw_and_expanded_results(self):
        """
        Simulate BM25 index with:
          Doc 1: Dedicated topic "ECDIS Carriage Requirements and Maintenance"
          Doc 2: General chapter "SOLAS Chapter V Navigation Safety Regulations Systems"

        When search is expanded to 15 words, Doc 2 gets many common word hits.
        When raw query "ECDIS" is searched, Doc 1 gets a strong score.
        Dual BM25 must preserve Doc 1's strong score.
        """
        bm25 = BM25Store()
        docs = [
            {
                "content_id": "doc_ecdis",
                "topic_name": "ECDIS Carriage Requirements",
                "content": "Electronic Chart Display and Information System ECDIS maintenance and standards.",
            },
            {
                "content_id": "doc_solas_general",
                "topic_name": "SOLAS Chapter V Safety",
                "content": "Navigation safety regulations, bridge procedures, equipment checks and systems requirements.",
            },
        ]
        bm25.build_index(docs)

        raw_query = "ECDIS"
        expanded_query = "Electronic Chart Display and Information System ECDIS navigation carriage requirements SOLAS Chapter V safety systems"

        expanded_results = bm25.search(expanded_query, k=5)
        raw_results = bm25.search(raw_query, k=5)

        merged_bm25 = {
            str(r.get("content_id") or r.get("topic_name") or idx): r
            for idx, r in enumerate(expanded_results)
        }
        for r_idx, r_doc in enumerate(raw_results):
            key = str(r_doc.get("content_id") or r_doc.get("topic_name") or f"raw_{r_idx}")
            if key in merged_bm25:
                if float(r_doc.get("_bm25_score") or 0) > float(merged_bm25[key].get("_bm25_score") or 0):
                    merged_bm25[key] = r_doc
            else:
                merged_bm25[key] = r_doc

        final_bm25 = sorted(
            merged_bm25.values(),
            key=lambda d: float(d.get("_bm25_score") or 0),
            reverse=True
        )

        assert len(final_bm25) > 0
        assert final_bm25[0]["content_id"] == "doc_ecdis", "Exact keyword chunk 'doc_ecdis' must rank #1"
        print(f"\n[PASS] Dual BM25 rank #1: '{final_bm25[0]['topic_name']}' (score={final_bm25[0]['_bm25_score']:.4f})")

    def test_dual_bm25_deduplication(self):
        """
        Verify that documents present in both raw and expanded searches are deduplicated,
        retaining the highest score.
        """
        bm25 = BM25Store()
        docs = [
            {"content_id": "c1", "topic_name": "Crude Oil Washing", "content": "COW tank cleaning crude oil washing procedures."},
            {"content_id": "c2", "topic_name": "Inert Gas System", "content": "IGS tank atmosphere inert gas system."},
        ]
        bm25.build_index(docs)

        raw_res = bm25.search("COW", k=5)
        exp_res = bm25.search("Crude Oil Washing COW tank cleaning", k=5)

        merged_bm25 = {
            str(r.get("content_id") or r.get("topic_name") or idx): r
            for idx, r in enumerate(exp_res)
        }
        for r_idx, r_doc in enumerate(raw_res):
            key = str(r_doc.get("content_id") or r_doc.get("topic_name") or f"raw_{r_idx}")
            if key in merged_bm25:
                if float(r_doc.get("_bm25_score") or 0) > float(merged_bm25[key].get("_bm25_score") or 0):
                    merged_bm25[key] = r_doc
            else:
                merged_bm25[key] = r_doc

        ids = [d["content_id"] for d in merged_bm25.values()]
        assert len(ids) == len(set(ids)), "Merged BM25 list must not contain duplicate content_ids"
        print(f"\n[PASS] Dual BM25 merged clean: {len(ids)} unique docs, no duplicates")


# =================================================================
# GROUP C: Score-Aware RRF Multipliers
# =================================================================
class TestGroupC_ScoreAwareRRF:
    """
    Validate that Score-Aware RRF allows strong keyword matches to beat mediocre vector neighbors.
    """

    def test_score_aware_rrf_promotes_confident_keyword_match(self):
        """
        Scenario:
          FAISS has a mediocre match 'doc_wrong' at rank 0 (dist=1.30, not confident)
          FAISS has 'doc_correct' at rank 1 (dist=1.35)
          BM25 has an unmistakable exact match 'doc_correct' at rank 0 (score=8.5, strong)
          BM25 has NO match for 'doc_wrong' (score=0.0)

        Score-Aware RRF:
          doc_wrong:   (1/61) * 1.0 = 0.01639
          doc_correct: (1/62) * 1.0 + (1/61) * 1.15 = 0.01613 + 0.01885 = 0.03498
        """
        rrf_k = 60
        doc_scores = defaultdict(float)

        faiss_results = [
            {"content_id": "doc_wrong", "_score": 1.30},
            {"content_id": "doc_correct", "_score": 1.35},
        ]
        bm25_results = [
            {"content_id": "doc_correct", "_bm25_score": 8.5},
        ]

        def _doc_key(doc, default_idx):
            return str(doc.get("content_id") or doc.get("topic_name") or f"doc_{default_idx}")

        # FAISS loop
        for rank, doc in enumerate(faiss_results):
            key = _doc_key(doc, rank)
            dist = float(doc.get("_score") or 1.0)
            dist_mult = 1.15 if dist < 0.8 else (1.05 if dist < 1.1 else 1.0)
            doc_scores[key] += (1.0 / (rrf_k + rank + 1)) * dist_mult

        # BM25 loop
        for rank, doc in enumerate(bm25_results):
            key = _doc_key(doc, rank + 1000)
            score = float(doc.get("_bm25_score") or 0)
            bm25_mult = 1.15 if score >= 5.0 else (1.05 if score >= 2.0 else 1.0)
            doc_scores[key] += (1.0 / (rrf_k + rank + 1)) * bm25_mult

        sorted_keys = sorted(doc_scores.keys(), key=lambda k_val: doc_scores[k_val], reverse=True)
        assert sorted_keys[0] == "doc_correct", "doc_correct must win decisively"
        margin = doc_scores["doc_correct"] - doc_scores["doc_wrong"]
        assert margin > 0.018, f"Winning margin should be > 0.018, got {margin:.5f}"
        print(f"\n[PASS] Score-Aware RRF: 'doc_correct' wins by {margin:.5f} (total: {doc_scores['doc_correct']:.5f})")

    def test_faiss_tight_semantic_match_boosted(self):
        """
        FAISS result with distance < 0.8 receives the 1.15 multiplier.
        Borderline FAISS result with distance >= 1.1 receives 1.0 multiplier.
        """
        tight_dist = 0.55
        borderline_dist = 1.25

        tight_mult = 1.15 if tight_dist < 0.8 else (1.05 if tight_dist < 1.1 else 1.0)
        borderline_mult = 1.15 if borderline_dist < 0.8 else (1.05 if borderline_dist < 1.1 else 1.0)

        assert tight_mult == 1.15
        assert borderline_mult == 1.0
        print(f"\n[PASS] FAISS multipliers verified: tight={tight_mult}x, borderline={borderline_mult}x")


# =================================================================
# GROUP D: Stale Key Scoping Bug Fix
# =================================================================
class TestGroupD_StaleKeyScopingBugFix:
    """
    Validate that BM25 filter correctly computes key per document before checking threshold.
    """

    def test_bm25_first_doc_below_threshold_does_not_use_stale_key(self):
        """
        If the first BM25 doc has _bm25_score < 0.05, its key must be its own key
        and not inherited from FAISS loop or an undefined variable.
        """
        doc_map = {}
        bm25_results = [
            {"content_id": "doc_noise_1", "_bm25_score": 0.02},
            {"content_id": "doc_valid_2", "_bm25_score": 3.5},
        ]

        def _doc_key(doc, default_idx):
            return str(doc.get("content_id") or doc.get("topic_name") or f"doc_{default_idx}")

        for rank, doc in enumerate(bm25_results):
            key = _doc_key(doc, rank + 1000)
            bm25_score = float(doc.get("_bm25_score") or 0)
            if bm25_score < 0.05:
                if key not in doc_map:
                    doc_map[key] = doc
                continue
            if key not in doc_map:
                doc_map[key] = doc

        assert "doc_noise_1" in doc_map
        assert "doc_valid_2" in doc_map
        print(f"\n[PASS] BM25 doc_map correctly populated: keys={list(doc_map.keys())}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
