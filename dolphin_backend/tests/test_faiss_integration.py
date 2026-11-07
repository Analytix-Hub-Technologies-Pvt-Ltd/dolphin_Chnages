# tests/test_faiss_integration.py
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from retrieval.faiss_store import FAISSStore
from services.embedding_config import EMBEDDING_DIM


def test_faiss_integration():
    """Test that FAISSStore works with the new search_with_embeddings method"""

    async def _run():
        print("🧪 Testing FAISSStore Integration")

        faiss_store = FAISSStore(EMBEDDING_DIM)
        faiss_store.load()
        assert faiss_store.dimension == EMBEDDING_DIM
        assert faiss_store.index.d == EMBEDDING_DIM

        print(f"📊 Store stats: {faiss_store.index.ntotal} documents loaded")

        if faiss_store.index.ntotal == 0:
            print("⚠️ FAISS store empty; skipping assertion-heavy checks")
            return

        test_query = "Ship Stability during Heavy Lift Operations"
        print(f"\n🔍 Testing search_with_embeddings: '{test_query}'")

        try:
            results = await faiss_store.search_with_embeddings(test_query, k=2)
            print(f"✅ search_with_embeddings successful! Found {len(results)} results")

            assert len(results) > 0, "Should find at least one result"

            for i, result in enumerate(results):
                title = result.get('title', 'No title')
                content = result.get('content', 'No content')
                print(f"   Result {i+1}: {title}")
                print(f"      Preview: {content[:100]}...")

        except Exception as e:
            print(f"❌ search_with_embeddings failed: {e}")
            assert False, f"search_with_embeddings raised an exception: {e}"

    asyncio.run(_run())
