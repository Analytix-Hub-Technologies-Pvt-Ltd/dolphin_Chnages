"""
run_live_retrieval_eval.py
==========================
Live End-to-End Evaluation of Retrieval & Answer Generation

Tests live questions:
  1. Short working query: "What is enclosed space entry on a ship?"
  2. Acronym query (previously failed/diluted): "What is COW crude oil washing procedure?"
  3. Long complex query (previously over-filtered): "What are the ECDIS route planning procedures in restricted visibility?"
  4. Regulatory query: "STCW Manila 2010 amendment on watchkeeping"

Evaluates:
  - Retrieved topic name & chunk match
  - Answer validity, accuracy, and completeness
"""

import sys
import os
from pathlib import Path
import asyncio
import time

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.dependencies import (
    get_openai_service,
    get_embedding_service,
    get_faiss_store,
    get_company_store,
    get_transcribe_store,
    get_bm25_store,
)
from models.database import get_pool
from services.chat_service import ChatService
from services.session_service import SessionService

TEST_QUESTIONS = [
    {
        "id": "Q1_SHORT",
        "query": "What is the procedure for enclosed space entry on a ship?",
        "expected_keywords": ["enclosed space", "entry", "atmosphere", "oxygen", "permit"],
        "category": "Standard Working Question (Regression Guard)"
    },
    {
        "id": "Q2_ACRONYM",
        "query": "What is COW crude oil washing procedure on oil tankers?",
        "expected_keywords": ["crude oil washing", "cow", "tank", "cargo", "inert gas"],
        "category": "Acronym Match (Dual BM25 Validation)"
    },
    {
        "id": "Q3_COMPLEX",
        "query": "What are the ECDIS route planning procedures in restricted visibility and heavy traffic conditions?",
        "expected_keywords": ["ecdis", "route", "planning", "safety", "cross track"],
        "category": "Complex Multi-Concept Query (Adaptive Threshold Validation)"
    },
    {
        "id": "Q4_REGULATORY",
        "query": "What are the STCW Manila 2010 amendments for watchkeeping hours of rest?",
        "expected_keywords": ["stcw", "manila", "rest", "hours", "watchkeeping"],
        "category": "Regulatory Rare-Term Query (BM25 Low Threshold Validation)"
    }
]

async def run_evaluation():
    print("=" * 80)
    print("LIVE RETRIEVAL & ANSWER GENERATION EVALUATION")
    print("=" * 80)
    print("Initializing services...")
    t0 = time.perf_counter()
    pool = await get_pool()
    openai_service = get_openai_service()
    embedder = get_embedding_service(openai_service)
    store = get_faiss_store()
    company_store = get_company_store()
    transcribe_store = get_transcribe_store()
    bm25 = get_bm25_store()
    session_service = SessionService(pool)

    chat_service = ChatService(
        openai_service,
        embedder,
        store,
        session_service,
        company_store=company_store,
        transcribe_store=transcribe_store,
        bm25_store=bm25,
    )
    print(f"Services initialized in {time.perf_counter() - t0:.2f}s\n")

    user_details = {
        "id": "eval_user",
        "name": "Evaluation Tester",
        "company_id": "1",
        "role": "Master / Chief Officer"
    }

    results = []

    for idx, item in enumerate(TEST_QUESTIONS, 1):
        q_id = item["id"]
        q_text = item["query"]
        category = item["category"]
        exp_kws = item["expected_keywords"]

        print(f"\n[{idx}/4] EVALUATING: {q_id} ({category})")
        print(f"Query: \"{q_text}\"")

        start_time = time.perf_counter()
        try:
            node_response, updated_messages, standalone_query, understanding_summary, extras = await chat_service.run_chat(
                user_id="eval_user",
                session_id=f"eval_session_{q_id}",
                db_messages=[],
                current_query=q_text,
                category=None,
                user_details=user_details
            )
            elapsed = time.perf_counter() - start_time

            content = getattr(node_response, "content", "") or ""
            sections = getattr(node_response, "sections", []) or []

            # Extract retrieved topic names
            retrieved_topics = []
            if sections:
                for s in sections:
                    if isinstance(s, dict) and s.get("topic_name"):
                        retrieved_topics.append(s["topic_name"])

            # Check keyword presence in answer
            content_lower = content.lower()
            matched_kws = [kw for kw in exp_kws if kw in content_lower]
            kw_match_ratio = len(matched_kws) / len(exp_kws) if exp_kws else 1.0

            is_valid = len(content) > 100 and kw_match_ratio >= 0.60

            status = "PASS" if is_valid else "REVIEW"
            print(f"Result: [{status}] (Elapsed: {elapsed:.2f}s)")
            print(f"Retrieved Topics: {retrieved_topics or 'Default / Generic'}")
            print(f"Answer Length: {len(content)} characters")
            print(f"Matched Keywords: {matched_kws} ({len(matched_kws)}/{len(exp_kws)})")
            print(f"Answer Preview: {content[:250].strip()}...\n")

            results.append({
                "id": q_id,
                "status": status,
                "topics": retrieved_topics,
                "matched_kws": matched_kws,
                "len": len(content),
                "preview": content[:180].replace("\n", " "),
                "elapsed": elapsed
            })

        except Exception as e:
            print(f"Result: [ERROR] {e}")
            results.append({
                "id": q_id,
                "status": "ERROR",
                "error": str(e)
            })

    print("=" * 80)
    print("EVALUATION SUMMARY REPORT")
    print("=" * 80)
    for r in results:
        status_tag = f"[{r['status']}]"
        print(f"{status_tag:<8} {r['id']:<15} | Length: {r.get('len', 0):<5} | Topics: {r.get('topics', [])} | {r.get('elapsed', 0):.2f}s")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_evaluation())
