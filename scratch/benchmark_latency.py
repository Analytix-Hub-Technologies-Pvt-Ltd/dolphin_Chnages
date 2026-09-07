import asyncio
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, ".")

from api.dependencies import get_openai_service, get_embedding_service, get_faiss_store, get_company_store, get_transcribe_store
from services.chat_service import ChatService
from services.session_service import SessionService
from models.database import get_pool

async def benchmark():
    pool = await get_pool()
    openai_service = get_openai_service()
    embedder = get_embedding_service(openai_service)
    store = get_faiss_store()
    company_store = get_company_store()
    transcribe_store = get_transcribe_store()
    session_service = SessionService(pool)
    
    chat_service = ChatService(
        openai_service=openai_service,
        embedder=embedder,
        store=store,
        session_service=session_service,
        company_store=company_store,
        transcribe_store=transcribe_store,
    )
    
    print("\n=======================================================")
    print("🚀 TEST 1: Standard Course Query (Cargo Unloading)")
    print("=======================================================")
    t0 = time.perf_counter()
    resp1, msgs1, standalone1, und1, extras1 = await chat_service.run_chat(
        user_id="bench-user-1",
        session_id="bench-session-1",
        db_messages=[],
        current_query="Explain cargo unloading process",
        category="QUERY",
        user_details={"role": "Chief Officer", "ship_type": "Oil Tanker"}
    )
    t1 = time.perf_counter()
    duration1 = t1 - t0
    print(f"⏱️ Total Latency: {duration1:.2f} seconds")
    print(f"✅ Response Type: {getattr(resp1, 'type', None)}")
    print(f"✅ Sections Count: {len(getattr(resp1, 'sections', []) or [])}")
    print(f"✅ Suggestions: {getattr(resp1, 'question_suggestions', [])[:2]}")
    print(f"📄 Content Preview (first 250 chars):\n{getattr(resp1, 'content', '')[:250]}...\n")
    
    print("\n=======================================================")
    print("🏢 TEST 2: Company SMS Query (Documentation Circulation)")
    print("=======================================================")
    t0 = time.perf_counter()
    resp2, msgs2, standalone2, und2, extras2 = await chat_service.run_chat(
        user_id="bench-user-2",
        session_id="bench-session-2",
        db_messages=[],
        current_query="What is the SMS procedure for documentation and circulation?",
        category="QUERY",
        user_details={
            "company_id": "8",
            "company_name": "CMS Demo Company",
            "role": "Master",
            "ship_type": "Chemical Tanker"
        }
    )
    t2 = time.perf_counter()
    duration2 = t2 - t0
    print(f"⏱️ Total Latency: {duration2:.2f} seconds")
    print(f"✅ Response Type: {getattr(resp2, 'type', None)}")
    content2 = getattr(resp2, 'content', '')
    print(f"✅ Has Section 1 (Company SMS): {'1. According to' in content2 or 'Safety Management System' in content2}")
    print(f"✅ Has Section 2 (Dolphin Knowledge): {'2. Dolphin internal knowledge' in content2}")
    print(f"✅ Has Section 3 (Comparison / Advisory): {'3. Comparison' in content2 or 'Advisory' in content2}")
    print(f"📄 Content Preview (first 400 chars):\n{content2[:400]}...\n")
    
    print("=======================================================")
    print("📊 BENCHMARK SUMMARY:")
    print(f"Course Query Latency:  {duration1:.2f}s  (Target: < 5.0s)")
    print(f"Company Query Latency: {duration2:.2f}s  (Target: < 5.0s)")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(benchmark())
