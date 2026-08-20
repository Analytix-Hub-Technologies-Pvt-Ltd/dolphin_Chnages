# tests/test_retrieval_working.py
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from retrieval.faiss_store import FAISSStore
from services.embedding_config import EMBEDDING_DIM
from services.openai_service import OpenAIService


def test_retrieval():
    """Test retrieval with the populated FAISS store"""

    async def _run():
        print("🧪 Testing FAISS Retrieval")

        openai_service = OpenAIService()
        faiss_store = FAISSStore(EMBEDDING_DIM)
        faiss_store.load()
        assert faiss_store.dimension == EMBEDDING_DIM
        assert faiss_store.index.d == EMBEDDING_DIM

        print(f"📊 Store stats: {faiss_store.index.ntotal} documents loaded")

        test_queries = [
            "Ship Stability Considerations during Heavy Lift Operations",
            "marine safety procedures",
            "ship propulsion systems",
            "buoyancy and stability"
        ]

        for query in test_queries:
            print(f"\n🔍 Testing query: '{query}'")

            query_embedding = await openai_service.embed(query)
            results = faiss_store.search(query_embedding, k=2)

            print(f"   Found {len(results)} results")

            for i, result in enumerate(results):
                title = result.get('title', 'No title')
                content_preview = result.get('content', 'No content')[:100] + "..."
                print(f"   Result {i+1}: {title}")
                print(f"      {content_preview}")

    asyncio.run(_run())


if __name__ == "__main__":
    asyncio.run(test_retrieval())
