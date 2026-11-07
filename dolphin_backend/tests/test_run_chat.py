import asyncio
import time
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

async def test_chat():
    print("Pre-warming singletons...")
    t0 = time.perf_counter()
    pool = await get_pool()
    openai_service = get_openai_service()
    embedder = get_embedding_service(openai_service)
    store = get_faiss_store()
    company_store = get_company_store()
    transcribe_store = get_transcribe_store()
    bm25 = get_bm25_store()
    session_service = SessionService(pool)
    print(f"Pre-warming completed in {time.perf_counter() - t0:.2f}s")

    chat_service = ChatService(
        openai_service,
        embedder,
        store,
        session_service,
        company_store=company_store,
        transcribe_store=transcribe_store,
        bm25_store=bm25,
    )

    query = "What is the procedure for enclosed space entry on a ship?"
    user_details = {"id": "test_user", "name": "Test User", "company_id": "1", "role": "Chief Officer"}

    print("\n--- Starting Query Execution Benchmark ---")
    start_time = time.perf_counter()

    node_response, updated_messages, standalone_query, understanding_summary, extras = await chat_service.run_chat(
        user_id="test_user",
        session_id="test_session_bench_1",
        db_messages=[],
        current_query=query,
        category=None,
        user_details=user_details
    )

    elapsed = time.perf_counter() - start_time
    print("\n==========================================")
    print(f"TOTAL EXECUTION TIME: {elapsed:.2f} seconds")
    print("==========================================")
    print("Type:", getattr(node_response, 'type', type(node_response)))
    print("Content preview:", (getattr(node_response, 'content', '') or '')[:200])
    if hasattr(node_response, 'sections') and node_response.sections:
        for idx, s in enumerate(node_response.sections):
            print(f"Section {idx+1} [topic={s.get('topic_name')}]: {s.get('content')[:100]}...")
    print("Question suggestions:", getattr(node_response, 'question_suggestions', []))
    print(f"Target < 10.0s: {'PASSED' if elapsed < 10.0 else 'FAILED'}")

if __name__ == "__main__":
    asyncio.run(test_chat())

