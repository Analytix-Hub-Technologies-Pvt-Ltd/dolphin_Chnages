# api/dependencies.py
from __future__ import annotations

from functools import lru_cache
from typing import AsyncGenerator

from fastapi import Depends
from loguru import logger

from models.database import get_pool
from retrieval.faiss_store import COMPANY_INDEX_PATH, COMPANY_META_PATH, TRANSCRIBE_INDEX_PATH, TRANSCRIBE_META_PATH, FAISSStore
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService


# ---------------------------------------------------------------------------
# CACHED SINGLETON OPENAI SERVICE
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_openai_service() -> OpenAIService:
    return OpenAIService()


# ---------------------------------------------------------------------------
# EMBEDDING SERVICE (depends on OpenAI)
# ---------------------------------------------------------------------------
def get_embedding_service(
    openai_service: OpenAIService = Depends(get_openai_service),
) -> EmbeddingService:
    return EmbeddingService(openai_service)


# ---------------------------------------------------------------------------
# FAISS STORE SINGLETON
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_faiss_store() -> FAISSStore:
    """
    ⚡ OPTIMIZATION: Load FAISS index ONCE and reuse across all requests.
    
    Previously created a new FAISSStore + read index from disk per request (~0.5-2s).
    Now cached as singleton — eliminates disk I/O on every request.

    FAISSStore.load() will:
    - load index if exists AND dims==3072 AND not empty
    - otherwise auto-rebuild from tutor_content
    """
    store = FAISSStore()
    store.load()
    logger.info("⚡ FAISS store loaded as singleton (cached)")
    return store

@lru_cache(maxsize=1)
def get_company_store() -> FAISSStore:
    company_store = FAISSStore(
        index_path=COMPANY_INDEX_PATH,
        meta_path=COMPANY_META_PATH,
    )

    company_store.load()
    return company_store

@lru_cache(maxsize=1)
def get_transcribe_store() -> FAISSStore:
    transcribe_store = FAISSStore(
        index_path= TRANSCRIBE_INDEX_PATH,
        meta_path= TRANSCRIBE_META_PATH,
    )

    transcribe_store.load()
    return transcribe_store


# ---------------------------------------------------------------------------
# BM25 STORE SINGLETON
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_bm25_store():
    """
    ⚡ BM25 keyword search index built over tutor_content / FAISS metadata chunks.
    Allows exact keyword lookups alongside dense FAISS vector searches.
    Loads instantly from pre-built disk cache if available.
    """
    from retrieval.bm25_store import BM25Store, BM25_CACHE_PATH
    import os
    bm25 = BM25Store()
    if os.path.exists(BM25_CACHE_PATH):
        if bm25.load_cache(BM25_CACHE_PATH):
            return bm25
    faiss_store = get_faiss_store()
    if faiss_store and faiss_store.id_to_metadata:
        bm25.build_index(faiss_store.id_to_metadata)
        bm25.save_cache(BM25_CACHE_PATH)
    return bm25


# ---------------------------------------------------------------------------
# ASYNC DB POOL (FastAPI dependency)
# ---------------------------------------------------------------------------
async def get_db_pool() -> AsyncGenerator:
    """
    Dependency that yields the global database pool.
    
    CRITICAL: Does NOT close the pool after the request!
    The pool is shared across all requests and is only closed 
    during application shutdown (in main.py lifespan).
    """
    pool = await get_pool()
    yield pool
    # DO NOT close the pool here - it's a shared global resource!


# ---------------------------------------------------------------------------
# APPROVED FEEDBACK MEMORY SERVICE
# ---------------------------------------------------------------------------
_approved_memory_service = None

async def get_approved_memory_service():
    """Get singleton instance of ApprovedMemoryService with embedder."""
    global _approved_memory_service
    if _approved_memory_service is None:
        from services.approved_memory_service import ApprovedMemoryService
        from services.embedding_service import EmbeddingService
        from services.openai_service import OpenAIService
        pool = await get_pool()
        embedder = EmbeddingService(OpenAIService())
        _approved_memory_service = ApprovedMemoryService(pool, embedder=embedder)
        await _approved_memory_service.init_table()
    return _approved_memory_service

