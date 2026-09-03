from __future__ import annotations

import asyncio
from typing import List

from loguru import logger

from services.openai_service import OpenAIService


EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 3072


class EmbeddingService:
    def __init__(self, openai_service: OpenAIService) -> None:
        self.openai_service = openai_service
        self.embedding_model = EMBEDDING_MODEL
        self.embedding_dim = EMBEDDING_DIM
        self._query_cache: dict[str, List[float]] = {}
        logger.info("🔧 Embedding model: text-embedding-3-large (3072 dims)")

    async def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """
        Embed multiple documents using batch API call.
        This is much faster than embedding one-by-one for large datasets.
        """
        if not documents:
            return []
        
        # Use the batch embedding method for efficiency
        embeddings = await self.openai_service.embed_batch(documents)
        
        # Validation already handled in embed_batch, but double-check
        fixed_embeddings: List[List[float]] = []
        for embedding in embeddings:
            if len(embedding) != self.embedding_dim:
                logger.warning(
                    "⚠️ Embedding dimension mismatch. Expected {}, got {}. Fixing length.",
                    self.embedding_dim,
                    len(embedding),
                )
                embedding = (embedding + [0.0] * self.embedding_dim)[: self.embedding_dim]
            fixed_embeddings.append(embedding)
        return fixed_embeddings

    async def embed_query(self, query: str) -> List[float]:
        cleaned = (query or "").strip().lower()
        if not cleaned:
            return [0.0] * self.embedding_dim
        if cleaned in self._query_cache:
            return self._query_cache[cleaned]

        embedding = await self.openai_service.embed(query)
        if len(embedding) != self.embedding_dim:
            logger.warning(
                "⚠️ Embedding dimension mismatch. Expected {}, got {}. Fixing length.",
                self.embedding_dim,
                len(embedding),
            )
            embedding = (embedding + [0.0] * self.embedding_dim)[: self.embedding_dim]

        if len(self._query_cache) > 1000:
            self._query_cache.pop(next(iter(self._query_cache)))
        self._query_cache[cleaned] = embedding
        return embedding

    def embed_text(self, text: str) -> List[float]:
        logger.error("🧠 Embedding input text = '{}'", text[:200])
        cleaned = (text or "").strip().lower()
        if cleaned and cleaned in self._query_cache:
            return self._query_cache[cleaned]
        embedding = asyncio.run(self.openai_service.embed(text))
        if len(embedding) != self.embedding_dim:
            logger.warning(
                "⚠️ Embedding dimension mismatch. Expected {}, got {}. Fixing length.",
                self.embedding_dim,
                len(embedding),
            )
            embedding = (embedding + [0.0] * self.embedding_dim)[: self.embedding_dim]
        if cleaned:
            if len(self._query_cache) > 1000:
                self._query_cache.pop(next(iter(self._query_cache)))
            self._query_cache[cleaned] = embedding
        return embedding

