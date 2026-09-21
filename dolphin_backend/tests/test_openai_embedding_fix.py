import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.embedding_config import EMBEDDING_DIM
from services.openai_service import OpenAIService
from retrieval.faiss_store import FAISSStore


def test_embedding_input_types():
    """Test the embedding service with various input types"""

    async def _run():
        print("🧪 Testing OpenAI Embedding with Various Input Types")
        print("=" * 60)

        openai_service = OpenAIService()

        test_cases = [
            ("Ship Stability Considerations during Heavy Lift Operations", "Normal string", True),
            ("", "Empty string", True),
            ("   ", "Whitespace string", True),
            (None, "None value", True),
            (["Ship", "Stability"], "List of strings", True),
            ([1, 2, 3], "List of numbers", True),
            (123, "Integer", True),
            (45.67, "Float", True),
            ({"key": "value"}, "Dictionary", True),
            ([], "Empty list", True),
        ]

        for test_input, description, expected_to_work in test_cases:
            print(f"\n🔍 Testing: {description}")
            print(f"   Input: {repr(test_input)} (type: {type(test_input).__name__})")

            try:
                embedding = await openai_service.embed(test_input)

                if embedding and len(embedding) == EMBEDDING_DIM and any(x != 0 for x in embedding):
                    print(f"   ✅ SUCCESS - Generated valid embedding ({len(embedding)} dimensions)")
                else:
                    print(f"   ⚠️  WARNING - Generated zero vector fallback")

            except Exception as e:
                print(f"   ❌ FAILED - {e}")

    asyncio.run(_run())


def test_faiss_integration():
    """Test FAISS store integration with the fixed embedding service"""

    async def _run():
        print("\n\n🧪 Testing FAISS Store Integration")
        print("=" * 60)

        faiss_store = FAISSStore(EMBEDDING_DIM)
        faiss_store.load()
        assert faiss_store.index.d == EMBEDDING_DIM

        print(f"📊 FAISS Store Stats:")
        print(f"   - Documents: {faiss_store.index.ntotal}")
        print(f"   - Dimension: {faiss_store.dimension}")

        if faiss_store.index.ntotal == 0:
            print("❌ No documents in FAISS store - run populate_faiss.py first!")
            return

        test_queries = [
            "Ship Stability during Heavy Lift Operations",
            "marine safety procedures",
            "ship propulsion systems",
            "",  # Empty query
            ["invalid", "list", "input"],  # Invalid input
        ]

        for query in test_queries:
            print(f"\n🔍 Testing query: {repr(query)}")

            try:
                results = await faiss_store.search_with_embeddings(query, k=2)
                print(f"   ✅ Found {len(results)} results")

                for i, result in enumerate(results):
                    title = result.get('title', 'No title')
                    content_preview = result.get('content', 'No content')[:80] + "..."
                    print(f"      {i+1}. {title}")
                    print(f"         {content_preview}")

            except Exception as e:
                print(f"   ❌ Failed: {e}")

    asyncio.run(_run())


def test_complete_retrieval_flow():
    """Test the complete retrieval flow"""

    async def _run():
        print("\n\n🧪 Testing Complete Retrieval Flow")
        print("=" * 60)

        from graph.retrieval_node import RetrievalNode

        test_state = {
            "current_query": "Ship Stability Considerations during Heavy Lift Operations",
            "retrieval_chunks": [],
            "video_suggestions": [],
            "meaningful_messages": [],
            "meaningful_history": [],
        }

        faiss_store = FAISSStore(EMBEDDING_DIM)
        faiss_store.load()
        assert faiss_store.index.d == EMBEDDING_DIM

        if faiss_store.index.ntotal == 0:
            print("❌ FAISS store is empty - cannot test retrieval flow")
            return

        retrieval_node = RetrievalNode(faiss_store)

        try:
            print("🔄 Running RetrievalNode...")
            result = await retrieval_node.run(test_state)

            chunks_count = len(result.get("retrieval_chunks", []))
            videos_count = len(result.get("video_suggestions", []))

            print(f"✅ RetrievalNode completed successfully!")
            print(f"   - Chunks retrieved: {chunks_count}")
            print(f"   - Videos suggested: {videos_count}")

            if chunks_count > 0:
                print("   📚 Retrieved chunks:")
                for i, chunk in enumerate(result["retrieval_chunks"][:2]):
                    print(f"      {i+1}. {chunk.get('title', 'No title')}")

        except Exception as e:
            print(f"❌ RetrievalNode failed: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(_run())


def main():
    """Run all tests"""
    print("🚀 Starting Comprehensive OpenAI Embedding Fix Tests")
    print("=" * 60)

    test_embedding_input_types()
    test_faiss_integration()
    test_complete_retrieval_flow()

    print("\n" + "=" * 60)
    print("🎉 All tests completed!")


if __name__ == "__main__":
    main()
