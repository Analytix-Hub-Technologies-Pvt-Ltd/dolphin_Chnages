from __future__ import annotations

import asyncio
import json
import math
import os
import pathlib
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.init_feedback_tables import INIT_FEEDBACK_SQL
from services.dpo_service import DPOService
from services.feedback_memory_service import FeedbackMemoryService, cosine_similarity
from services.feedback_service import FeedbackService
from pipeline.query import query_node


# ---------------------------------------------------------------------------
# In-Memory AsyncPG Mock Database Helpers
# ---------------------------------------------------------------------------

class MockAsyncpgRecord(dict):
    """Dict-like record compatible with asyncpg Record."""
    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


class MockDatabase:
    """In-memory database backing mock asyncpg connection."""
    def __init__(self):
        self.feedback_records: Dict[str, Dict[str, Any]] = {}
        self.approved_feedback_memory: Dict[str, Dict[str, Any]] = {}
        self.dpo_dataset: Dict[int, Dict[str, Any]] = {}
        self.dpo_training_jobs: Dict[str, Dict[str, Any]] = {}
        self.dpo_id_seq = 1

    def reset(self):
        self.feedback_records.clear()
        self.approved_feedback_memory.clear()
        self.dpo_dataset.clear()
        self.dpo_training_jobs.clear()
        self.dpo_id_seq = 1


class MockConnection:
    def __init__(self, db: MockDatabase):
        self.db = db

    async def execute(self, query: str, *args):
        q = " ".join(query.strip().upper().split())

        # CREATE / INDEX statements
        if q.startswith("CREATE") or q.startswith("ALTER") or q.startswith("--"):
            return "CREATE 1"

        # INSERT INTO feedback_records
        if "INSERT INTO PUBLIC.FEEDBACK_RECORDS" in q:
            f_id = args[0]
            self.db.feedback_records[f_id] = {
                "feedback_id": f_id,
                "user_id": args[1],
                "conversation_id": args[2],
                "message_id": args[3],
                "question": args[4],
                "original_response": args[5],
                "feedback_type": args[6],
                "feedback_comment": args[7],
                "company_id": args[8],
                "ship_type": args[9],
                "source_metadata": args[10],
                "status": args[11],
                "preferred_response": None,
                "rejection_reason": None,
                "reviewed_by": None,
                "reviewed_at": None,
                "admin_comment": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            return "INSERT 0 1"

        # UPDATE feedback_records on approve
        if "FEEDBACK_RECORDS" in q and "STATUS = 'APPROVED'" in q:
            f_id = args[4]
            if f_id in self.db.feedback_records:
                self.db.feedback_records[f_id].update({
                    "status": "approved",
                    "question": args[0],
                    "preferred_response": args[1],
                    "reviewed_by": args[2],
                    "admin_comment": args[3],
                    "reviewed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                })
            return "UPDATE 1"

        # UPDATE feedback_records on reject
        if "FEEDBACK_RECORDS" in q and "STATUS = 'REJECTED'" in q:
            f_id = args[3]
            if f_id in self.db.feedback_records:
                self.db.feedback_records[f_id].update({
                    "status": "rejected",
                    "rejection_reason": args[0],
                    "reviewed_by": args[1],
                    "admin_comment": args[2],
                    "reviewed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                })
            return "UPDATE 1"

        # UPDATE feedback_records general
        if "FEEDBACK_RECORDS" in q and "SET QUESTION = $1" in q:
            f_id = args[6]
            if f_id in self.db.feedback_records:
                self.db.feedback_records[f_id].update({
                    "question": args[0],
                    "preferred_response": args[1],
                    "reviewed_by": args[2],
                    "admin_comment": args[3],
                    "company_id": args[4],
                    "ship_type": args[5],
                    "updated_at": datetime.now(timezone.utc),
                })
            return "UPDATE 1"

        # DELETE approved_feedback_memory by ANY ids (supersede)
        if "DELETE FROM PUBLIC.APPROVED_FEEDBACK_MEMORY" in q and "MEMORY_ID = ANY" in q:
            stale_ids = args[0]
            for m_id in stale_ids:
                self.db.approved_feedback_memory.pop(m_id, None)
            return f"DELETE {len(stale_ids)}"

        # DELETE approved_feedback_memory by feedback_id
        if "DELETE FROM PUBLIC.APPROVED_FEEDBACK_MEMORY" in q and "FEEDBACK_ID = $1" in q:
            f_id = args[0]
            to_del = [m_id for m_id, v in self.db.approved_feedback_memory.items() if v["feedback_id"] == f_id]
            for m_id in to_del:
                del self.db.approved_feedback_memory[m_id]
            return f"DELETE {len(to_del)}"

        # INSERT / UPSERT approved_feedback_memory
        if "INSERT INTO PUBLIC.APPROVED_FEEDBACK_MEMORY" in q:
            m_id = args[0]
            self.db.approved_feedback_memory[m_id] = {
                "memory_id": m_id,
                "feedback_id": args[1],
                "question": args[2],
                "preferred_response": args[3],
                "original_response": args[4],
                "company_id": args[5],
                "ship_type": args[6],
                "embedding": args[7],
                "approved_by": args[8],
                "approved_at": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            return "INSERT 0 1"

        # UPDATE dpo_dataset
        if "UPDATE PUBLIC.DPO_DATASET" in q:
            if "STATUS = 'IN_TRAINING'" in q:
                for row in self.db.dpo_dataset.values():
                    if row.get("status") == "pending_training":
                        row["status"] = "in_training"
                return "UPDATE 1"
            if len(args) >= 7:
                f_id = args[6]
                for d_id, row in self.db.dpo_dataset.items():
                    if row["feedback_id"] == f_id:
                        row.update({
                            "prompt": args[0],
                            "chosen": args[1],
                            "rejected": args[2],
                            "company_id": args[3],
                            "ship_type": args[4],
                            "dataset_version": args[5],
                            "updated_at": datetime.now(timezone.utc),
                        })
            return "UPDATE 1"

        # INSERT dpo_training_jobs
        if "INSERT INTO PUBLIC.DPO_TRAINING_JOBS" in q:
            j_id = args[0]
            self.db.dpo_training_jobs[j_id] = {
                "job_id": j_id,
                "company_id": args[1],
                "dataset_version": args[2],
                "example_count": args[3],
                "base_model": args[4],
                "status": "queued",
                "output_model": None,
                "error_message": None,
                "started_at": None,
                "completed_at": None,
                "created_at": datetime.now(timezone.utc),
            }
            return "INSERT 0 1"

        # UPDATE dpo_training_jobs status
        if "DPO_TRAINING_JOBS" in q and "STATUS = $1" in q:
            new_status = args[0]
            out_model = args[1]
            err_msg = args[2]
            j_id = args[3]
            if j_id in self.db.dpo_training_jobs:
                self.db.dpo_training_jobs[j_id].update({
                    "status": new_status,
                    "output_model": out_model,
                    "error_message": err_msg,
                })
            return "UPDATE 1"

        # DELETE feedback_records
        if "DELETE FROM PUBLIC.FEEDBACK_RECORDS" in q and "FEEDBACK_ID = $1" in q:
            f_id = args[0]
            if f_id in self.db.feedback_records:
                del self.db.feedback_records[f_id]
                return "DELETE 1"
            return "DELETE 0"

        return "OK"

    async def fetch(self, query: str, *args):
        q = " ".join(query.strip().upper().split())

        # 1. Superseding candidates in approved_feedback_memory (2 args: company, exclude_fid)
        if "APPROVED_FEEDBACK_MEMORY" in q and "FEEDBACK_ID !=" in q:
            company = args[0]
            exclude_fid = args[1]
            results = []
            for row in self.db.approved_feedback_memory.values():
                if (row["company_id"] == company or row["company_id"] == "global") and row["feedback_id"] != exclude_fid:
                    results.append(MockAsyncpgRecord(row))
            return results

        # 2. Vector search lookup in approved_feedback_memory (1 arg: user_company)
        if "APPROVED_FEEDBACK_MEMORY" in q and ("PREFERRED_RESPONSE" in q or "COMPANY_ID = $1" in q):
            user_company = args[0]
            results = []
            for row in self.db.approved_feedback_memory.values():
                if row["company_id"] == user_company or row["company_id"] == "global":
                    results.append(MockAsyncpgRecord(row))
            return results

        # 3. KPI counts in get_dashboard_analytics (GROUP BY status)
        if "FEEDBACK_RECORDS" in q and "GROUP BY STATUS" in q:
            status_counts = Counter(r.get("status") for r in self.db.feedback_records.values())
            return [MockAsyncpgRecord({"status": s, "count": c}) for s, c in status_counts.items()]

        # 4. Trend query in get_dashboard_analytics (GROUP BY day)
        if "FEEDBACK_RECORDS" in q and "GROUP BY DAY" in q:
            today_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            total = len(self.db.feedback_records)
            pos = sum(1 for r in self.db.feedback_records.values() if r.get("status") == "positive")
            neg = total - pos
            return [MockAsyncpgRecord({"day": today_dt, "total": total, "positive": pos, "negative": neg})]

        # 5. Issue category breakdown (GROUP BY feedback_type)
        if "FEEDBACK_RECORDS" in q and "GROUP BY FEEDBACK_TYPE" in q:
            cat_counts = Counter(r.get("feedback_type") for r in self.db.feedback_records.values() if r.get("feedback_type") != "positive")
            return [MockAsyncpgRecord({"feedback_type": cat, "count": count}) for cat, count in cat_counts.items()]

        # 6. Pending aging query (WHERE status = 'pending')
        if "FEEDBACK_RECORDS" in q and "STATUS = 'PENDING'" in q and "ORDER BY CREATED_AT" in q:
            pending_rows = [r for r in self.db.feedback_records.values() if r.get("status") == "pending"]
            return [MockAsyncpgRecord(r) for r in pending_rows]

        # 7. Reviewer throughput (GROUP BY reviewed_by)
        if "FEEDBACK_RECORDS" in q and "GROUP BY REVIEWED_BY" in q:
            rev_map = defaultdict(lambda: {"total": 0, "approved": 0, "rejected": 0})
            for r in self.db.feedback_records.values():
                rev = r.get("reviewed_by")
                if rev:
                    rev_map[rev]["total"] += 1
                    if r.get("status") == "approved":
                        rev_map[rev]["approved"] += 1
                    elif r.get("status") == "rejected":
                        rev_map[rev]["rejected"] += 1
            return [
                MockAsyncpgRecord({
                    "reviewed_by": rev,
                    "total": stats["total"],
                    "approved": stats["approved"],
                    "rejected": stats["rejected"],
                })
                for rev, stats in rev_map.items()
            ]

        # 8. Company analytics breakdown (GROUP BY company)
        if "FEEDBACK_RECORDS" in q and "GROUP BY COMPANY" in q:
            comp_map = defaultdict(lambda: {"total": 0, "positive": 0, "pending": 0, "approved": 0, "rejected": 0})
            for r in self.db.feedback_records.values():
                c = r.get("company_id") or "Unassigned"
                comp_map[c]["total"] += 1
                if r.get("status") == "positive":
                    comp_map[c]["positive"] += 1
                elif r.get("status") == "pending":
                    comp_map[c]["pending"] += 1
                elif r.get("status") == "approved":
                    comp_map[c]["approved"] += 1
                elif r.get("status") == "rejected":
                    comp_map[c]["rejected"] += 1
            return [
                MockAsyncpgRecord({
                    "company": c,
                    "total": stats["total"],
                    "positive": stats["positive"],
                    "pending": stats["pending"],
                    "approved": stats["approved"],
                    "rejected": stats["rejected"],
                })
                for c, stats in comp_map.items()
            ]

        # 9. Ship type analytics breakdown (GROUP BY ship_type)
        if "FEEDBACK_RECORDS" in q and "GROUP BY SHIP_TYPE" in q:
            ship_map = defaultdict(lambda: {"total": 0, "positive": 0, "pending": 0, "approved": 0, "rejected": 0})
            for r in self.db.feedback_records.values():
                s = r.get("ship_type") or "Unassigned"
                ship_map[s]["total"] += 1
                if r.get("status") == "positive":
                    ship_map[s]["positive"] += 1
                elif r.get("status") == "pending":
                    ship_map[s]["pending"] += 1
                elif r.get("status") == "approved":
                    ship_map[s]["approved"] += 1
                elif r.get("status") == "rejected":
                    ship_map[s]["rejected"] += 1
            return [
                MockAsyncpgRecord({
                    "ship_type": s,
                    "total": stats["total"],
                    "positive": stats["positive"],
                    "pending": stats["pending"],
                    "approved": stats["approved"],
                    "rejected": stats["rejected"],
                })
                for s, stats in ship_map.items()
            ]

        # 10. Live Recent Events
        if "FEEDBACK_RECORDS" in q and "LIMIT 10" in q:
            return [MockAsyncpgRecord(r) for r in list(self.db.feedback_records.values())[:10]]

        # 11. List feedback records general
        if "FEEDBACK_RECORDS" in q and "WHERE 1=1" in q:
            return [MockAsyncpgRecord(r) for r in self.db.feedback_records.values()]

        # 12. Export DPO dataset
        if "DPO_DATASET" in q and "WHERE 1=1" in q:
            return [MockAsyncpgRecord(r) for r in self.db.dpo_dataset.values()]

        # 13. List DPO training jobs
        if "DPO_TRAINING_JOBS" in q:
            return [MockAsyncpgRecord(r) for r in self.db.dpo_training_jobs.values()]

        # 14. Topic search
        if "CURRICULUM_TOPICS" in q or "COMPANY_DOCS" in q:
            return [
                MockAsyncpgRecord({
                    "topic_code": "SOP_BUNKERING_01",
                    "topic_name": "Bunkering Safety Checklist",
                    "category": "Curriculum SOP",
                    "snippet": "Pre-bunkering containment and scupper plug verification protocol."
                }),
                MockAsyncpgRecord({
                    "topic_code": "SOP_CONFINED_SPACE",
                    "topic_name": "Enclosed Space Entry Permit",
                    "category": "Company Manual",
                    "snippet": "Multi-gas detector atmosphere testing threshold standards."
                })
            ]

        return []

    async def fetchrow(self, query: str, *args):
        q = " ".join(query.strip().upper().split())
        if "FEEDBACK_RECORDS" in q and "FEEDBACK_ID = $1" in q:
            f_id = args[0]
            if f_id in self.db.feedback_records:
                return MockAsyncpgRecord(self.db.feedback_records[f_id])
            return None

        if "APPROVED_FEEDBACK_MEMORY" in q and "FEEDBACK_ID = $1" in q:
            f_id = args[0]
            for row in self.db.approved_feedback_memory.values():
                if row["feedback_id"] == f_id:
                    return MockAsyncpgRecord(row)
            return None

        if "DPO_TRAINING_JOBS" in q and "JOB_ID = $1" in q:
            j_id = args[0]
            if j_id in self.db.dpo_training_jobs:
                return MockAsyncpgRecord(self.db.dpo_training_jobs[j_id])
            return None

        return None

    async def fetchval(self, query: str, *args):
        q = " ".join(query.strip().upper().split())

        if "DPO_DATASET" in q and "FEEDBACK_ID = $1" in q:
            f_id = args[0]
            for d_id, row in self.db.dpo_dataset.items():
                if row["feedback_id"] == f_id:
                    return d_id
            return None

        if "INSERT INTO PUBLIC.DPO_DATASET" in q and "RETURNING DPO_ID" in q:
            d_id = self.db.dpo_id_seq
            self.db.dpo_id_seq += 1
            self.db.dpo_dataset[d_id] = {
                "dpo_id": d_id,
                "feedback_id": args[0],
                "company_id": args[1],
                "ship_type": args[2],
                "prompt": args[3],
                "chosen": args[4],
                "rejected": args[5],
                "status": "pending_training",
                "dataset_version": args[6],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            return d_id

        if "COUNT(*)" in q:
            if "APPROVED_FEEDBACK_MEMORY" in q:
                return len(self.db.approved_feedback_memory)
            if "FEEDBACK_RECORDS" in q and "STATUS = 'PENDING'" in q:
                return sum(1 for r in self.db.feedback_records.values() if r.get("status") == "pending")
            if "DPO_DATASET" in q:
                return len(self.db.dpo_dataset)
            if "FEEDBACK_RECORDS" in q:
                return len(self.db.feedback_records)

        return 0


class MockPool:
    def __init__(self, db: MockDatabase):
        self.db = db

    def acquire(self):
        conn = MockConnection(self.db)
        class PoolAcquireContext:
            async def __aenter__(self):
                return conn
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        return PoolAcquireContext()


# ---------------------------------------------------------------------------
# Mock Embedding & OpenAI Services
# ---------------------------------------------------------------------------

class MockEmbeddingService:
    def __init__(self):
        self.embeddings_map: Dict[str, List[float]] = {}

    async def embed_query(self, query: str) -> List[float]:
        q_clean = query.strip().lower()
        if q_clean in self.embeddings_map:
            return self.embeddings_map[q_clean]

        # Generate deterministic synthetic unit vector based on text hash
        val = sum(ord(c) for c in q_clean)
        dim = 16  # compact for testing
        vec = [math.sin(val + i) for i in range(dim)]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        unit_vec = [x / norm for x in vec]
        return unit_vec


class MockOpenAIService:
    def __init__(self):
        self.response_text = "Verified standard SOP procedure: 1. Verify oxygen level >20.9%. 2. Issue entry permit. 3. Station standby watcher."

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        return self.response_text


# ---------------------------------------------------------------------------
# TEST FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    return MockDatabase()


@pytest.fixture
def mock_pool(mock_db):
    return MockPool(mock_db)


@pytest.fixture
def mock_embedder():
    return MockEmbeddingService()


@pytest.fixture
def mock_openai():
    return MockOpenAIService()


@pytest.fixture
def memory_service(mock_pool, mock_embedder):
    return FeedbackMemoryService(pool=mock_pool, embedder=mock_embedder)


@pytest.fixture
def dpo_service(mock_pool):
    return DPOService(pool=mock_pool)


@pytest.fixture
def feedback_service(mock_pool, memory_service, dpo_service, mock_openai):
    return FeedbackService(
        pool=mock_pool,
        memory_service=memory_service,
        dpo_service=dpo_service,
        openai_service=mock_openai,
    )


# ===========================================================================
# 1. Cosine Similarity Edge Case Unit Tests
# ===========================================================================

def test_cosine_similarity_edge_cases():
    # Identical vectors -> 1.0
    v1 = [1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v1), 0.001) == 1.0

    # Orthogonal vectors -> 0.0
    v2 = [0.0, 1.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v2), 0.001) == 0.0

    # Opposites -> -1.0
    v3 = [-1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v3), 0.001) == -1.0

    # Empty or mismatched dimensions -> 0.0
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


# ===========================================================================
# 2. Ingestion Tests (Positive vs Negative Categorization)
# ===========================================================================

@pytest.mark.anyio
async def test_submit_positive_feedback(feedback_service, mock_db):
    res = await feedback_service.submit_feedback(
        question="What is the flashpoint of marine diesel?",
        original_response="Marine diesel oil has a minimum flashpoint of 60°C as per SOLAS.",
        feedback_type="positive",
        feedback_comment="Great concise explanation!",
        user_id="chief_eng_01",
        company_id="maersk",
        ship_type="container",
    )

    assert res["status"] == "positive"
    assert res["feedback_type"] == "positive"
    assert res["feedback_id"].startswith("fb_")
    assert res["feedback_id"] in mock_db.feedback_records

    rec = mock_db.feedback_records[res["feedback_id"]]
    assert rec["status"] == "positive"
    assert rec["user_id"] == "chief_eng_01"
    assert rec["company_id"] == "maersk"
    assert rec["ship_type"] == "container"


@pytest.mark.anyio
async def test_submit_negative_feedback_queues_for_moderation(feedback_service, mock_db):
    res = await feedback_service.submit_feedback(
        question="What are the procedures for entering an enclosed space?",
        original_response="Just open the hatch and enter immediately.",
        feedback_type="safety_compliance",
        feedback_comment="Dangerous! Missing atmospheric test and permit to work.",
        user_id="safety_officer_9",
        company_id="chevron_marine",
        ship_type="oil_tanker",
    )

    assert res["status"] == "pending"
    assert res["feedback_type"] == "safety_compliance"
    assert res["feedback_id"] in mock_db.feedback_records

    rec = mock_db.feedback_records[res["feedback_id"]]
    assert rec["status"] == "pending"
    assert rec["feedback_comment"] == "Dangerous! Missing atmospheric test and permit to work."


# ===========================================================================
# 3. Moderation & Validation Tests
# ===========================================================================

@pytest.mark.anyio
async def test_rejection_requires_mandatory_reason(feedback_service, mock_db):
    sub = await feedback_service.submit_feedback(
        question="How to test bilge alarm?",
        original_response="Press the test toggle on console.",
        feedback_type="incomplete_context",
    )
    fid = sub["feedback_id"]

    # Reject with empty or whitespace reason must raise ValueError
    with pytest.raises(ValueError, match="Rejection reason is mandatory"):
        await feedback_service.reject_feedback(
            feedback_id=fid,
            rejection_reason="",
            reviewer_id="lead_sme",
        )

    with pytest.raises(ValueError, match="Rejection reason is mandatory"):
        await feedback_service.reject_feedback(
            feedback_id=fid,
            rejection_reason="   ",
            reviewer_id="lead_sme",
        )

    # Valid rejection
    res = await feedback_service.reject_feedback(
        feedback_id=fid,
        rejection_reason="The original response is already fully accurate according to maker manual.",
        reviewer_id="lead_sme",
        admin_comment="Verified against Daihatsu generator documentation.",
    )

    assert res["status"] == "rejected"
    assert res["rejection_reason"] == "The original response is already fully accurate according to maker manual."
    assert mock_db.feedback_records[fid]["status"] == "rejected"


@pytest.mark.anyio
async def test_approve_indexes_memory_and_dpo_pair(feedback_service, mock_db):
    sub = await feedback_service.submit_feedback(
        question="What is the maximum oily water separator discharge limit?",
        original_response="Discharge is permitted at 50 ppm.",
        feedback_type="regulatory_violation",
        company_id="maersk",
        ship_type="container",
    )
    fid = sub["feedback_id"]

    verified_answer = "Under MARPOL Annex I, the maximum permitted oil content in discharged bilge water is strictly 15 ppm with an active 15 ppm bilge alarm and automatic stopping device."

    res = await feedback_service.approve_feedback(
        feedback_id=fid,
        preferred_response=verified_answer,
        question="What is the maximum oily water separator discharge limit under MARPOL?",
        reviewer_id="marine_superintendent",
        company_id="maersk",
        ship_type="container",
    )

    assert res["status"] == "approved"
    assert res["feedback_id"] == fid
    assert res["memory_id"] == f"mem_{fid}"
    assert res["dpo_id"] is not None

    # Verify feedback_records update
    assert mock_db.feedback_records[fid]["status"] == "approved"
    assert mock_db.feedback_records[fid]["preferred_response"] == verified_answer

    # Verify vector memory index
    mem = mock_db.approved_feedback_memory[f"mem_{fid}"]
    assert mem["preferred_response"] == verified_answer
    assert mem["company_id"] == "maersk"
    assert mem["ship_type"] == "container"

    # Verify DPO pair
    dpo_row = mock_db.dpo_dataset[res["dpo_id"]]
    assert dpo_row["chosen"] == verified_answer
    assert dpo_row["rejected"] == "Discharge is permitted at 50 ppm."


# ===========================================================================
# 4. AI-Assisted Response Regeneration Tests
# ===========================================================================

@pytest.mark.anyio
async def test_regenerate_preferred_response(feedback_service, mock_openai, mock_db):
    sub = await feedback_service.submit_feedback(
        question="Bunker manifold checklist prior to bunkering?",
        original_response="Connect hose and open valve.",
        feedback_type="incorrect_procedure",
        company_id="v_ships",
    )
    fid = sub["feedback_id"]

    mock_openai.response_text = "Standard Bunkering Protocol:\n1. Verify bunker checklist signed by Chief Engineer.\n2. Plug all deck scuppers.\n3. Test emergency stop."

    regen = await feedback_service.regenerate_preferred_response(
        feedback_id=fid,
        topic="SOP_BUNKERING_SAFETY",
        reference_text="Company safety management manual section 4.2: Scuppers must be plugged and drip trays dry.",
        reviewer_instructions="Emphasize scupper plugs and emergency shutdown communication.",
    )

    assert "generated_preferred_response" in regen
    assert "Standard Bunkering Protocol" in regen["generated_preferred_response"]


# ===========================================================================
# 5. Semantic Vector Memory & Multi-Tenant Isolation Tests
# ===========================================================================

@pytest.mark.anyio
async def test_feedback_memory_multi_tenant_isolation(memory_service, mock_embedder):
    # Setup test vectors
    vec_q1 = [1.0, 0.0, 0.0, 0.0] + [0.0] * 12
    vec_q2 = [0.99, 0.05, 0.0, 0.0] + [0.0] * 12

    mock_embedder.embeddings_map["how to calibrate oily water separator 15ppm monitor?"] = vec_q1
    mock_embedder.embeddings_map["how to test 15ppm bilge monitor?"] = vec_q2

    # Save memory under company 'bp_shipping'
    await memory_service.save_approved_memory(
        feedback_id="fb_tenant_1",
        question="how to calibrate oily water separator 15ppm monitor?",
        preferred_response="BP Shipping Standard: Use fresh calibration fluid and log in oily water record book.",
        original_response="Turn potentiometer screw.",
        company_id="bp_shipping",
        ship_type="oil_tanker",
        approved_by="bp_tech_lead",
    )

    # User from 'bp_shipping' should find it
    res_bp = await memory_service.find_relevant_feedback_preference(
        query="how to test 15ppm bilge monitor?",
        user_profile={"company_id": "bp_shipping", "ship_type": "oil_tanker"},
        min_similarity_threshold=0.65,
    )
    assert res_bp is not None
    assert "BP Shipping Standard" in res_bp["preferred_response"]

    # User from 'shell_marine' should NOT see bp_shipping memory (Multi-Tenant Isolation)
    res_shell = await memory_service.find_relevant_feedback_preference(
        query="how to test 15ppm bilge monitor?",
        user_profile={"company_id": "shell_marine", "ship_type": "oil_tanker"},
        min_similarity_threshold=0.65,
    )
    assert res_shell is None


@pytest.mark.anyio
async def test_feedback_memory_ship_affinity_boost(memory_service, mock_embedder):
    # Base similarity ~0.63 (below 0.65 threshold without boost)
    # With ship type match (+0.05 boost), effective similarity reaches ~0.68 (> 0.65 threshold)
    mock_embedder.embeddings_map["engine room crane operation"] = [1.0, 0.0] + [0.0] * 14
    mock_embedder.embeddings_map["crane safety limits"] = [0.63, 0.7766] + [0.0] * 14

    await memory_service.save_approved_memory(
        feedback_id="fb_ship_boost",
        question="crane safety limits",
        preferred_response="Check SWL (Safe Working Load) and limit switches before hoisting.",
        original_response="Operate crane at full speed.",
        company_id="global",
        ship_type="bulk_carrier",
    )

    # Non-matching ship type -> raw similarity 0.63 < 0.65 -> None
    res_no_match = await memory_service.find_relevant_feedback_preference(
        query="engine room crane operation",
        user_profile={"company_id": "global", "ship_type": "container"},
        min_similarity_threshold=0.65,
    )
    assert res_no_match is None

    # Matching ship type -> effective similarity 0.63 + 0.05 = 0.68 >= 0.65 -> Matched!
    res_match = await memory_service.find_relevant_feedback_preference(
        query="engine room crane operation",
        user_profile={"company_id": "global", "ship_type": "bulk_carrier"},
        min_similarity_threshold=0.65,
    )
    assert res_match is not None
    assert res_match["effective_similarity"] >= 0.65


@pytest.mark.anyio
async def test_feedback_memory_superseding_duplicates(memory_service, mock_embedder, mock_db):
    # Old memory
    vec_exact = [1.0, 0.0] + [0.0] * 14
    mock_embedder.embeddings_map["emergency steering gear test protocol"] = vec_exact
    mock_embedder.embeddings_map["emergency steering gear test"] = vec_exact

    await memory_service.save_approved_memory(
        feedback_id="fb_v1",
        question="emergency steering gear test protocol",
        preferred_response="V1 steering test standard.",
        original_response="old bad",
        company_id="global",
    )
    assert "mem_fb_v1" in mock_db.approved_feedback_memory

    # New approved memory with near-identical question (sim >= 0.92)
    await memory_service.save_approved_memory(
        feedback_id="fb_v2",
        question="emergency steering gear test",
        preferred_response="V2 updated SOLAS Reg V/26 steering test standard.",
        original_response="old bad 2",
        company_id="global",
    )

    # Old memory should be superseded and removed
    assert "mem_fb_v1" not in mock_db.approved_feedback_memory
    assert "mem_fb_v2" in mock_db.approved_feedback_memory
    assert mock_db.approved_feedback_memory["mem_fb_v2"]["preferred_response"] == "V2 updated SOLAS Reg V/26 steering test standard."


# ===========================================================================
# 6. Chat Pipeline Direct Response & Enrichment Routing Tests
# ===========================================================================

@pytest.mark.anyio
async def test_query_node_direct_delivery_when_similarity_high(mock_openai):
    state = {
        "user_query": "What is the flashpoint of marine gasoil?",
        "feedback_preference": {
            "feedback_id": "fb_flashpoint_verified",
            "question": "What is the flashpoint of marine gasoil?",
            "preferred_response": "Per ISO 8217 and SOLAS Reg II-2/4, the minimum flashpoint for marine gasoil is 60°C.",
            "raw_similarity": 0.95,
            "effective_similarity": 0.95,
        },
        "retrieved_chunks": [],
        "user_profile": {"name": "Alex", "company_name": "Oceanic"},
        "meaningful_history": [],
        "meaningful_messages": [],
    }

    result = await query_node(state, openai_service=mock_openai, suggestion_service=MagicMock())
    node_resp = result["node_response"]

    assert node_resp["metadata"]["source_badge"] == "Approved Feedback Memory (Verified Standard)"
    assert node_resp["metadata"]["routing_reason"] == "approved_feedback_memory"
    assert "minimum flashpoint for marine gasoil is 60°C" in node_resp["content"]


@pytest.mark.anyio
async def test_query_node_enrichment_when_similarity_moderate(mock_openai):
    state = {
        "user_query": "Bunkering safety pre-checks?",
        "feedback_preference": {
            "feedback_id": "fb_bunker_enrich",
            "question": "Bunkering pre-transfer safety checks?",
            "preferred_response": "Verified standard: All deck scuppers must be firmly plugged and save-all trays drained.",
            "raw_similarity": 0.70,
            "effective_similarity": 0.70,
        },
        "retrieved_chunks": [{"text": "Bunkering procedures outline transfer lines.", "videos": [], "images": [], "pdfs": []}],
        "user_profile": {"name": "Chief", "company_name": "V-Ships"},
        "meaningful_history": [],
        "meaningful_messages": [],
    }

    mock_openai.response_text = '{"sections": [{"topic_code": "BUNKER_01", "topic_name": "Bunkering", "content": "Scuppers plugged."}], "suggestions": []}'
    result = await query_node(state, openai_service=mock_openai, suggestion_service=MagicMock())

    node_resp = result["node_response"]
    assert node_resp["type"] == "query"
    assert len(node_resp["sections"]) > 0


# ===========================================================================
# 7. DPO Dataset & Training Jobs Tests
# ===========================================================================

@pytest.mark.anyio
async def test_dpo_dataset_and_training_lifecycle(dpo_service, mock_db):
    # Add preference pair
    dpo_id = await dpo_service.add_dpo_pair(
        feedback_id="fb_dpo_1",
        prompt="How to purge cargo tanks with inert gas?",
        chosen="Reduce oxygen content to <8% by volume and maintain positive pressure.",
        rejected="Vent directly with air.",
        company_id="tankers_corp",
        ship_type="lng_carrier",
        dataset_version="v1.0",
    )
    assert dpo_id > 0
    assert len(mock_db.dpo_dataset) == 1

    # Export dataset
    dataset = await dpo_service.export_dataset(format_type="jsonl")
    assert len(dataset) == 1
    assert dataset[0]["prompt"] == "How to purge cargo tanks with inert gas?"
    assert dataset[0]["chosen"] == "Reduce oxygen content to <8% by volume and maintain positive pressure."
    assert dataset[0]["rejected"] == "Vent directly with air."

    # Create training job
    job = await dpo_service.create_training_job(
        company_id="tankers_corp",
        dataset_version="v1.0",
        base_model="gpt-4o-mini",
    )
    assert job["status"] == "queued"
    assert job["job_id"].startswith("dpo_job_")

    # Update job status
    upd = await dpo_service.update_job_status(
        job_id=job["job_id"],
        status="completed",
        output_model="ft:gpt-4o-mini:tankers-corp-v1.0",
    )
    assert upd is True
    assert mock_db.dpo_training_jobs[job["job_id"]]["status"] == "completed"
    assert mock_db.dpo_training_jobs[job["job_id"]]["output_model"] == "ft:gpt-4o-mini:tankers-corp-v1.0"


# ===========================================================================
# 8. Analytics & Dashboard KPI Tests
# ===========================================================================

@pytest.mark.anyio
async def test_dashboard_analytics_calculations(feedback_service, mock_db):
    # Seed 3 records
    # 1. Positive
    await feedback_service.submit_feedback(
        question="Positive question 1",
        original_response="Good answer 1",
        feedback_type="positive",
        company_id="nordic_tankers",
    )
    # 2. Pending
    sub_pending = await feedback_service.submit_feedback(
        question="Pending question 2",
        original_response="Bad answer 2",
        feedback_type="factual_error",
        company_id="nordic_tankers",
    )
    # 3. Approved
    sub_approved = await feedback_service.submit_feedback(
        question="Approved question 3",
        original_response="Bad answer 3",
        feedback_type="safety_compliance",
        company_id="nordic_tankers",
    )
    await feedback_service.approve_feedback(
        feedback_id=sub_approved["feedback_id"],
        preferred_response="Approved Standard Answer 3",
        question="Approved question 3",
        reviewer_id="captain_sme",
        company_id="nordic_tankers",
    )

    analytics = await feedback_service.get_dashboard_analytics(date_range="30d")

    kpis = analytics["kpis"]
    assert kpis["total_feedback"] == 3
    assert kpis["positive_count"] == 1
    assert kpis["negative_count"] == 2
    assert pytest.approx(kpis["satisfaction_rate"], 0.1) == 33.3

    assert "trend" in analytics
    assert "category_breakdown" in analytics
    assert "resolution_status" in analytics
    assert "aging_buckets" in analytics
    assert "reviewer_stats" in analytics
    assert "company_analytics" in analytics
    assert "ship_analytics" in analytics
    assert "recent_activity" in analytics
