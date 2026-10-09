import asyncio
from models.database import get_pool
from services.approved_memory_service import ApprovedMemoryService
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService

async def test():
    pool = await get_pool()
    embedder = EmbeddingService(OpenAIService())
    svc = ApprovedMemoryService(pool, embedder=embedder)
    
    queries = [
        "What is the procedure for enclosed space entry on a ship?",
        "What are the enclosed space entry requirements?",
        "CENTRIFUGAL PUMPS",
        "how do i start the emergency fire pump and what valves to check?",
        "tell me about centrifugal pumps",
    ]
    for q in queries:
        res = await svc.search_approved_memory(q, company_id=None)
        print(f"\nQuery: {q}")
        if res:
            print(f"-> MATCH FOUND (id={res['feedback_id']}, type={res['match_type']}, score={res['score']})")
            print(f"-> Response snippet: {res['preferred_response'][:100]}...")
        else:
            print("-> NO MATCH FOUND")

if __name__ == "__main__":
    asyncio.run(test())
