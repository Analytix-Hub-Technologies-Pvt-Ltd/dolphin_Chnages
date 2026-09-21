from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import faiss
import numpy as np
from loguru import logger

from config import settings
from retrieval.bm25 import BM25Index
from services.embedding_config import EMBEDDING_DIM

# Default: top K for search
DEFAULT_TOP_K: int = settings.faiss_knn

# Store FAISS index here
DEFAULT_INDEX_PATH = os.path.join(os.path.dirname(__file__), "faiss_index.bin")
DEFAULT_META_PATH = os.path.join(os.path.dirname(__file__), "faiss_index.meta.json")

COMPANY_INDEX_PATH = os.path.join(os.path.dirname(__file__),"company_index.bin")
COMPANY_META_PATH = os.path.join(os.path.dirname(__file__),"company_index.meta.json")

TRANSCRIBE_INDEX_PATH = os.path.join(os.path.dirname(__file__),"transcribe_index.bin")
TRANSCRIBE_META_PATH = os.path.join(os.path.dirname(__file__),"transcribe_index.meta.json")
class FAISSStore:
    """
    Thin wrapper around a FAISS index + sidecar metadata + in-memory BM25 index.

    - index: FAISS vector index
    - id_to_metadata: list[dict] with course_content info
    - bm25_index: in-memory BM25Okapi inverted index for precision lexical retrieval
    """

    def __init__(
        self,
        index_path: str | int = DEFAULT_INDEX_PATH,
        meta_path: str = DEFAULT_META_PATH,
    ) -> None:
        if isinstance(index_path, int):
            self.dimension = index_path
            self.index_path = DEFAULT_INDEX_PATH
        else:
            self.dimension = EMBEDDING_DIM
            self.index_path = index_path

        self.meta_path = meta_path
        self.index: Optional[faiss.Index] = None
        self.id_to_metadata: List[Dict[str, Any]] = []
        self.bm25_index: Optional[BM25Index] = None
        self.is_loaded: bool = False

    def _init_bm25(self) -> None:
        """Initialize in-memory BM25 inverted index from metadata in background thread."""
        if not getattr(settings, "bm25_enabled", True):
            logger.debug("[BM25] Lexical search disabled in settings")
            return
        if not self.id_to_metadata:
            return
        
        import threading
        def _build():
            try:
                bm25 = BM25Index()
                bm25.build(self.id_to_metadata)
                self.bm25_index = bm25
                logger.info("✅ [BM25] Background build complete")
            except Exception as e:
                logger.warning(f"Failed to build BM25 index on FAISSStore: {e}")
                self.bm25_index = None

        thread = threading.Thread(target=_build, daemon=True)
        thread.start()

    # --------------------------------------------------------
    # Persistence
    # --------------------------------------------------------
    def load(self) -> None:
        """Load FAISS index + metadata from disk if present."""
        if self.is_loaded:
            logger.debug("FAISSStore.load(): already loaded")
            if self.bm25_index is None and self.id_to_metadata and getattr(settings, "bm25_enabled", True):
                self._init_bm25()
            return

        if not os.path.exists(self.index_path):
            logger.warning("FAISSStore.load(): index file not found at {}", self.index_path)
            self.index = faiss.IndexFlatL2(self.dimension)
            self.id_to_metadata = []
            self.is_loaded = True
            self._init_bm25()
            return

        logger.info("📦 Loading FAISS index from {}", self.index_path)
        self.index = faiss.read_index(self.index_path)

        if os.path.exists(self.meta_path):
            with open(self.meta_path, "r", encoding="utf-8") as f:
                self.id_to_metadata = json.load(f)
        else:
            logger.warning("FAISSStore.load(): metadata file not found at {}", self.meta_path)
            self.id_to_metadata = []

        self.is_loaded = True
        self._init_bm25()
        logger.success(
            "✅ FAISS index loaded — vectors={}, dim={}",
            self.index.ntotal if self.index is not None else 0,
            EMBEDDING_DIM,
        )

    def save(self) -> None:
        """Persist FAISS index + metadata to disk."""
        if self.index is None:
            logger.warning("FAISSStore.save(): no index to save")
            return

        logger.info("💾 Saving FAISS index to {}", self.index_path)
        faiss.write_index(self.index, self.index_path)

        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.id_to_metadata, f, ensure_ascii=False)

        logger.success(
            "✅ FAISS index + metadata saved (vectors={})",
            self.index.ntotal,
        )

    # --------------------------------------------------------
    # Build/Reset
    # --------------------------------------------------------
    def reset(self) -> None:
        """Reset to empty index + metadata."""
        logger.info("🧹 Resetting FAISS store (in-memory only)")
        self.index = None
        self.id_to_metadata = []
        self.is_loaded = False

    def build_from_embeddings(
        self,
        embeddings: np.ndarray,
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """
        Build FAISS index from an array of embeddings and matching metadata.
        embeddings: shape (N, EMBEDDING_DIM)
        """
        if embeddings.size == 0:
            logger.warning("build_from_embeddings(): no embeddings passed, creating empty store")
            self.reset()
            self.is_loaded = True
            return

        if embeddings.ndim != 2 or embeddings.shape[1] != EMBEDDING_DIM:
            raise ValueError(
                f"Embeddings shape mismatch. Expected (?, {EMBEDDING_DIM}), got {embeddings.shape}"
            )

        logger.info(
            "🏗️ Building FAISS index from embeddings — rows={}, dim={}",
            embeddings.shape[0],
            embeddings.shape[1],
        )

        # L2 index (you can swap to IP/cosine if needed with normalization)
        index = faiss.IndexFlatL2(EMBEDDING_DIM)
        index.add(embeddings.astype("float32"))

        self.index = index
        self.id_to_metadata = list(metadatas)
        self.is_loaded = True

        logger.success(
            "✅ New FAISS index built — ntotal={}",
            self.index.ntotal,
        )

    # --------------------------------------------------------
    # Query
    # --------------------------------------------------------
    def get_all_topic_names(self) -> List[str]:
        """
        Extract all unique topic names from the metadata.
        Used for fuzzy matching and suggestions.
        
        Returns:
            List of unique topic names from the database
        """
        if not self.is_loaded:
            logger.warning("FAISSStore.get_all_topic_names(): index not loaded, calling load() lazily")
            self.load()
        
        if not self.id_to_metadata:
            logger.warning("FAISSStore.get_all_topic_names(): no metadata available")
            return []
        
        topic_names = []
        for metadata in self.id_to_metadata:
            if not isinstance(metadata, dict):
                continue
            
            # Try multiple fields where topic name might be stored
            topic = (
                metadata.get('topic_name') or 
                metadata.get('title') or 
                metadata.get('Topic Name') or
                metadata.get('name') or
                ''
            )
            
            if topic and isinstance(topic, str):
                topic_names.append(topic.strip())
        
        # Return unique topics
        unique_topics = list(set(topic_names))
        logger.info(f"[FAISS] Extracted {len(unique_topics)} unique topic names from {len(self.id_to_metadata)} metadata entries")
        
        return unique_topics
    
    def search(self, query_vector: List[float], k: int = DEFAULT_TOP_K) -> List[Dict[str, Any]]:
        """
        Perform a vector search against the FAISS index.

        query_vector: 1D list/array length EMBEDDING_DIM
        k: how many results to return
        """
        if not self.is_loaded:
            logger.warning("FAISSStore.search(): index not loaded, calling load() lazily")
            self.load()

        if self.index is None or self.index.ntotal == 0:
            logger.warning("FAISSStore.search(): no vectors in index")
            return []

        # Normalise k
        k = max(1, min(k, self.index.ntotal))

        q = np.array(query_vector, dtype="float32").reshape(1, -1)
        if q.shape[1] != EMBEDDING_DIM:
            raise ValueError(
                f"Query vector dim mismatch. Expected {EMBEDDING_DIM}, got {q.shape[1]}"
            )

        logger.debug("🔍 FAISSStore.search() → running search with k={}", k)
        distances, indices = self.index.search(q, k)  # shape (1, k)

        results: List[Dict[str, Any]] = []
        for rank, (idx, dist) in enumerate(zip(indices[0], distances[0])):
            if idx < 0 or idx >= len(self.id_to_metadata):
                continue

            meta = dict(self.id_to_metadata[idx])
            meta["_rank"] = int(rank)
            meta["_score"] = float(dist)
            meta["_faiss_index"] = int(idx)
            logger.error(
                "🔸 SEARCH HIT idx={} rank={} score={:.4f} topic='{}'\npreview='{}...'",
                idx,
                rank,
                dist,
                meta.get("topic_name"),
                str(meta.get("content", ""))[:150].replace("\n", " "),
            )
            results.append(meta)

        logger.info("✅ FAISSStore.search() → {} results", len(results))
        return results

    async def search_with_embeddings(self, query: str, k: int = DEFAULT_TOP_K) -> List[Dict[str, Any]]:
        """
        Perform a vector search against the FAISS index by first embedding the query text.
        """
        from services.openai_service import OpenAIService
        openai_service = OpenAIService()
        query_vector = await openai_service.embed(query)
        return self.search(query_vector, k=k)

    def add_embeddings( self, embeddings: list[list[float]], metadatas: list[dict[str, Any]], ) -> None: 
        
        """ Incrementally add new embeddings and metadata to the existing FAISS index.
         
        Args: 
            embeddings: List of embedding vectors. metadatas: Matching metadata for each embedding. """
            
        if len(embeddings) != len(metadatas): 
            raise ValueError( "Embeddings and metadata count mismatch." ) 
        
        vectors = np.asarray(embeddings, dtype="float32" ) 
        
        if vectors.ndim != 2 or vectors.shape[1] != EMBEDDING_DIM: 
            raise ValueError( f"Embedding shape mismatch. " f"Expected (?, {EMBEDDING_DIM}), got {vectors.shape}" ) 
        
        # If no index exists yet, create one 
        
        if self.index is None: 
            logger.info("Creating new FAISS index...") 
            self.index = faiss.IndexFlatL2( EMBEDDING_DIM ) 
            self.id_to_metadata = [] 
            self.is_loaded = True 
        logger.info( "Adding {} vectors to FAISS index...", len(vectors) ) 
        
        # ensure correct dtype 
        vectors = vectors.astype("float32") 
        
        if self.index is None: # defensive: should not happen because we create above, but guard anyway 
            raise RuntimeError("FAISS index is not initialized") 
        
        self.index.add(vectors) 
        self.id_to_metadata.extend( metadatas ) 
        
        logger.success( "Added {} vectors. Total vectors = {}", len(vectors), self.index.ntotal)

    def search_bm25(self, query: str, k: int = 50, filter_fn=None) -> List[Dict[str, Any]]:
        """Perform a lexical BM25 search over the stored metadata."""
        if not self.is_loaded:
            self.load()
        if self.bm25_index is None:
            return []
        return self.bm25_index.search(query=query, k=k, filter_fn=filter_fn)

    async def search_hybrid(
        self,
        original_query: str,
        expanded_query: str = None,
        k: int = 10,
        filter_fn=None,
        topic_filter=None,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Execute hybrid search combining FAISS vector search on expanded query
        and BM25 lexical search on original query with precision scoring.
        """
        from retrieval.precision_scorer import (
            compute_chunk_precision_score,
            rank_and_filter_candidates,
        )

        if not self.is_loaded:
            self.load()

        eff_expanded = expanded_query or original_query
        vector_cands = []
        try:
            all_vector = await self.search_with_embeddings(eff_expanded, k=max(k * 3, 50))
            for c in all_vector:
                if filter_fn is None or filter_fn(c):
                    vector_cands.append(c)
        except Exception as e:
            logger.warning(f"FAISS vector search failed in search_hybrid: {e}")
            vector_cands = []

        bm25_cands = []
        if self.bm25_index is not None and getattr(settings, "bm25_enabled", True):
            try:
                bm25_cands = self.bm25_index.search(query=original_query, k=max(k * 3, 50), filter_fn=filter_fn)
            except Exception as e:
                logger.warning(f"BM25 search failed in search_hybrid: {e}")
                bm25_cands = []

        merged_map: Dict[Any, Dict[str, Any]] = {}
        max_bm25 = 1.0
        for c in bm25_cands:
            b_score = float(c.get("_bm25_score", 0.0) or 0.0)
            if b_score > max_bm25:
                max_bm25 = b_score

        for c in vector_cands:
            key = c.get("content_id") or c.get("id") or c.get("_faiss_index")
            if key is not None:
                merged_map[key] = dict(c)

        for c in bm25_cands:
            key = c.get("content_id") or c.get("id") or c.get("_faiss_index")
            if key is not None:
                if key in merged_map:
                    merged_map[key]["_bm25_score"] = c.get("_bm25_score")
                else:
                    merged_map[key] = dict(c)

        all_cands = list(merged_map.values())
        if not all_cands:
            return [], None, {"status": "empty"}

        filtered_chunks, exact_topic, debug_info_list = rank_and_filter_candidates(
            candidates=all_cands,
            query=original_query,
            standalone_query=expanded_query or original_query,
            top_k=k,
        )

        debug_info = {
            "total_candidates": len(all_cands),
            "vector_candidates": len(vector_cands),
            "bm25_candidates": len(bm25_cands),
            "exact_topic_detected": bool(exact_topic),
            "exact_topic": exact_topic,
        }

        return filtered_chunks[:k], exact_topic, debug_info


