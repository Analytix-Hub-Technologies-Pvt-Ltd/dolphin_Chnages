# Phase 3 Retrieval Enhancement: Architecture & Implementation Plan

> **Status:** Saved for Future Implementation  
> **Target Modules:** `backend/graph/retrieval_node.py`, `backend/retrieval/bm25_store.py`, `backend/pipeline/retrieval.py`  
> **Prerequisites Completed:** Phase 1 (Thresholds & Wider K) & Phase 2 (Dual BM25 & Score-Aware RRF) — all 17 unit tests passing.

---

## 1. Executive Summary & Goals

Phase 1 and Phase 2 successfully resolved query expansion keyword dilution, rare-term BM25 dropouts, and long-query distance over-filtering. Live evaluations against the production database and OpenAI GPT models confirmed a **100% success rate on test queries**.

Phase 3 is the **final fine-tuning stage** designed to address remaining subtle edge cases in topic disambiguation, BM25 term-frequency weighting, and cross-pipeline consistency:
1. **Subtopic Disambiguation:** Prevent broad generic overview topics from beating specific operational procedure chunks.
2. **BM25 Single-Word De-Biasing:** Prevent single broad words (e.g. *"Safety"*, *"Maintenance"*) from artificially inflating BM25 scores due to title doubling.
3. **Cross-Pipeline Re-Ranking Alignment:** Ensure graph orchestration (`retrieval_node.py`) and direct pipeline orchestration (`retrieval.py`) share identical temporal and regulatory re-ranking weights.

---

## 2. Detailed Technical Breakdown

### Item 1: Subtopic Priority in Re-Ranking
- **Affected File:** `backend/graph/retrieval_node.py` (`_rerank_by_topic_match`)
- **The Issue:**
  When multiple courses or topics share a primary subject keyword (for example, `ECDISOverview`, `ECDISRoutePlanning`, and `ECDISAlarms`), a specific question like *"How do I plan a route on ECDIS?"* matches the word `"ECDIS"` across all candidate chunks. If `ECDISOverview` happens to have a slightly closer generic semantic embedding, it can remain ranked at #1 even though the user explicitly requested *"route planning"*.
- **The Solution:**
  Enhance `_rerank_by_topic_match` to distinguish **Primary Domain Subject** from **Specific Operational Action**:
  - Detect multi-token queries where one token is the domain anchor (e.g., `ECDIS`, `COW`, `Oily Water Separator`) and secondary tokens represent actions/aspects (e.g., `route planning`, `checklist`, `alarm`, `calibration`, `emergency`, `procedure`).
  - Award an extra compound boost ($+0.35$) when **both** the domain anchor and the specific operational aspect match the candidate chunk's topic name or header metadata.

### Item 2: BM25 Single-Word Generic Topic De-Biasing
- **Affected File:** `backend/retrieval/bm25_store.py` (L108)
- **The Issue:**
  Line 108 of `bm25_store.py` builds the index text as:
  ```python
  text = f"{topic} {topic} {content}".strip()
  ```
  Doubling the topic name was intended to give topic headers higher prominence. However, for broad single-word topics like `"Safety"`, `"Maintenance"`, or `"Overview"`, any user question containing the common word "maintenance" gives that generic document an artificially doubled BM25 term-frequency score ($TF$).
- **The Solution:**
  Apply conditional topic doubling during BM25 index creation:
  - If `len(topic.split()) >= 2` or topic is an acronym/specialized code (e.g. `ECDIS`, `STCW`, `SOLAS`, `MARPOL`): double the topic name (`f"{topic} {topic} {content}"`).
  - If `topic` is a single broad conversational word (e.g., `Safety`, `Overview`, `Maintenance`, `General`): index the topic name once (`f"{topic} {content}"`) to avoid score skewing.
  *(Note: Takes effect when the BM25 store is initialized or reloaded).*

### Item 3: Cross-Pipeline Re-Ranking Alignment
- **Affected Files:** `backend/pipeline/retrieval.py` & `backend/graph/retrieval_node.py`
- **The Issue:**
  `retrieval_node.py` in the graph execution flow has advanced content-aware temporal and regulatory constraint boosting (e.g., rewarding chunks matching specific amendment years like `2024`, `2026` or conventions like `MEPC`, `SEEMP`, `STCW`). The standalone pipeline path in `retrieval.py` used a slightly simpler re-ranking pass.
- **The Solution:**
  Refactor temporal and regulatory constraint re-ranking into a shared helper function in `retrieval/reranker.py` or import it directly so both execution flows apply the exact same boost weights.

---

## 3. Implementation Checklist (For When Ready to Build)

When team authorization is given to execute Phase 3:
1. [ ] **Step 1 — Create Unit Test Suite (`backend/tests/test_phase3_retrieval_fixes.py`):**
   - Test group for subtopic compound boost (`ECDISRoutePlanning` vs `ECDISOverview`).
   - Test group for single-word topic de-biasing in `bm25_store.py`.
   - Test group asserting pipeline vs graph re-ranking parity.
2. [ ] **Step 2 — Code Implementation:**
   - Update `_rerank_by_topic_match` in `backend/graph/retrieval_node.py`.
   - Update `_build_index` in `backend/retrieval/bm25_store.py`.
   - Align `backend/pipeline/retrieval.py` with graph re-ranking logic.
3. [ ] **Step 3 — Verification:**
   - Run complete test suite: Phase 1 (10 tests) + Phase 2 (7 tests) + Phase 3 tests.
   - Run live end-to-end evaluation with `backend/tests/run_live_retrieval_eval.py`.
4. [ ] **Step 4 — Documentation & Git:**
   - Update `CHANGELOG.md` with Phase 3 entry, exact line numbers, and verification traces.
