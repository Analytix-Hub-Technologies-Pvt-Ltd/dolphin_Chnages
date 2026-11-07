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

async def test():
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

    query = "Explain the key differences between two-stroke and four-stroke marine diesel engines"
    user_details = {"id": "test_user_engine", "name": "Test User", "company_id": "1", "role": "Chief Engineer"}

    print("Running query...")
    t0 = time.perf_counter()
    node_response, updated_messages, standalone_query, understanding_summary, extras = await chat_service.run_chat(
        user_id="test_user_engine",
        session_id="test_session_engine_1",
        db_messages=[],
        current_query=query,
        category=None,
        user_details=user_details
    )
    elapsed = time.perf_counter() - t0
    print(f"Elapsed: {elapsed:.2f}s")
    print("Content length:", len(getattr(node_response, 'content', '') or ''))
    print("Sections:", len(getattr(node_response, 'sections', []) or []))

if __name__ == "__main__":
    asyncio.run(test())
