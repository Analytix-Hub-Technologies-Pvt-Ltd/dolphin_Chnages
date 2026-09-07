import asyncio
import sys
sys.path.insert(0, ".")
from api.dependencies import get_openai_service, get_embedding_service, get_faiss_store, get_db_pool
from services.chat_service import ChatService
from services.session_service import SessionService
from models.database import get_pool

async def test_cargo():
    pool = await get_pool()
    openai_service = get_openai_service()
    embedder = get_embedding_service(openai_service)
    store = get_faiss_store()
    session_service = SessionService(pool)
    
    chat_service = ChatService(openai_service, embedder, store, session_service)
    
    resp, msgs, standalone, und, extras = await chat_service.run_chat(
        user_id="test-user",
        session_id="test-session-cargo",
        db_messages=[],
        current_query="Explain cargo unloading process",
        category="QUERY",
        user_details={"role": "Chief Officer", "ship_type": "Oil Tanker"}
    )
    
    print("STATUS TYPE:", getattr(resp, "type", None))
    print("CONTENT PREVIEW:\n", getattr(resp, "content", "")[:500])
    print("SECTIONS COUNT:", len(getattr(resp, "sections", []) or []))

if __name__ == "__main__":
    asyncio.run(test_cargo())
