# test_retrieval.py
import asyncio
import sys
from pathlib import Path

# Add your project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from retrieval.faiss_store import FAISSStore
from services.embedding_config import EMBEDDING_DIM
from services.embedding_service import EmbeddingService


class _DummyOpenAIService:
    async def embed(self, text: str):
        return [0.0] * EMBEDDING_DIM

    async def embed_batch(self, texts: list[str]):
        return [[0.0] * EMBEDDING_DIM for _ in texts]


def test_retrieval():
    """Test if retrieval is working"""

    async def _run():
        vector_store = FAISSStore(EMBEDDING_DIM)
        vector_store.load()
        assert vector_store.dimension == EMBEDDING_DIM
        assert vector_store.index.d == EMBEDDING_DIM

        embedder = EmbeddingService(_DummyOpenAIService())
        docs = ["Ship Stability", "Marine Safety"]
        embedded_vectors = await embedder.embed_documents(docs)
        assert all(len(v) == EMBEDDING_DIM for v in embedded_vectors)

    asyncio.run(_run())


if __name__ == "__main__":
    asyncio.run(test_retrieval())
