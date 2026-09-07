import asyncio
import json
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, ".")

from api.dependencies import get_openai_service, get_embedding_service, get_faiss_store, get_company_store, get_transcribe_store
from services.chat_service import ChatService
from models.database import get_pool

async def test():
    pool = await get_pool()
    chat_service = ChatService(
        openai_service=get_openai_service(),
        embedder=get_embedding_service(),
        store=get_faiss_store(),
        company_store=get_company_store(),
        transcribe_store=get_transcribe_store(),
    )

    query = "Explain firefighting procedures and appliances on ships"
    resp, msgs, standalone, und, extras = await chat_service.run_chat(
        user_id="1",
        session_id="firefighting-test-session",
        db_messages=[],
        current_query=query,
        category="QUERY",
        user_details={
            "company_id": "",
            "company_name": "",
            "role": "Chief Officer",
            "ship_type": "Gas Carrier"
        },
        standalone_query=query,
    )

    print("\n✅ Response Received!")
    print(f"Content length: {len(resp.content)}")
    print(f"Videos count: {len(extras.get('videos', []))}")
    for v in extras.get('videos', [])[:3]:
        print(f"  - Video: {v.get('title')} ({v.get('url')})")

    print(f"Images count: {len(extras.get('images', []))}")
    for img in extras.get('images', []):
        print(f"  - Image: {img.get('title')} (url={img.get('url')}, has_b64={bool(img.get('base64'))})")

if __name__ == "__main__":
    asyncio.run(test())
