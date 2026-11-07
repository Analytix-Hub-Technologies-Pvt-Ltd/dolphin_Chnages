import asyncio
from models.database import get_pool
from services.approved_memory_service import ApprovedMemoryService
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService

async def test():
    pool = await get_pool()
    embedder = EmbeddingService(OpenAIService())
    svc = ApprovedMemoryService(pool, embedder=embedder)
    
    test_queries = [
        "What is the procedure for enclosed space entry on a ship?", # exact
        "what is the procedure for enclosed space entry on a ship",  # case/punctuation
        "procedure for enclosed space entry on a ship",              # rewritten
        "enclosed space entry procedure",                            # short
        "tell me how to enter an enclosed space safely",             # paraphrased
    ]
    
    for q in test_queries:
        res = await svc.search_approved_memory(q, company_id=None, similarity_threshold=0.65)
        print(f"\nQuery: {q}")
        if res:
            print(f"-> MATCH: id={res['feedback_id']}, type={res['match_type']}, score={res.get('score', 0):.3f}")
            print(f"-> Response: {repr(res['preferred_response'][:80])}")
        else:
            print("-> NO MATCH")

if __name__ == "__main__":
    asyncio.run(test())
