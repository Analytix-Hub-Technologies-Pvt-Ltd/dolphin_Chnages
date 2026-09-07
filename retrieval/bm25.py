# retrieval/bm25.py
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger
from retrieval.normalization import (
    normalize_text_for_retrieval,
    tokenize_for_retrieval,
    simple_stem,
    QUERY_STOP_WORDS,
)


class BM25Index:
    """
    High-performance in-memory BM25Okapi index with inverted posting lists.
    Built once from corpus metadata and cached for repeated queries.
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        epsilon: float = 0.25,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.epsilon = epsilon

        self.corpus_size: int = 0
        self.avgdl: float = 0.0
        self.doc_lengths: List[int] = []
        
        # Inverted index: term -> list of (doc_idx, term_freq)
        self.inverted_index: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        
        # Term IDFs: term -> idf
        self.idf: Dict[str, float] = {}
        
        # Reference to raw metadata list
        self.metadatas: List[Dict[str, Any]] = []
        self.is_built: bool = False

    def build(self, metadatas: List[Dict[str, Any]]) -> None:
        """
        Build inverted index and compute IDFs from document metadata list.
        """
        if not metadatas:
            logger.warning("[BM25] Empty metadata list passed to BM25Index.build()")
            self.corpus_size = 0
            self.avgdl = 0.0
            self.doc_lengths = []
            self.inverted_index.clear()
            self.idf.clear()
            self.metadatas = []
            self.is_built = True
            return

        self.metadatas = list(metadatas)
        self.corpus_size = len(metadatas)
        self.doc_lengths = []
        self.inverted_index = defaultdict(list)

        df: Dict[str, int] = Counter()
        total_len = 0

        for doc_idx, meta in enumerate(metadatas):
            if not isinstance(meta, dict):
                self.doc_lengths.append(0)
                continue

            # Extract text fields: topic_name / title + topic_content / content
            topic_name = str(
                meta.get("topic_name")
                or meta.get("title")
                or meta.get("document_title")
                or ""
            )
            content = str(
                meta.get("topic_content")
                or meta.get("content")
                or meta.get("text")
                or ""
            )

            # Tokenize topic name and content with stemming
            # Extra weight to topic_name tokens by including them multiple times in document representation
            topic_tokens = tokenize_for_retrieval(topic_name, stem=True)
            content_tokens = tokenize_for_retrieval(content, stem=True)

            # Combine tokens (topic tokens weighted 3x for BM25 term frequency)
            doc_tokens = (topic_tokens * 3) + content_tokens
            doc_len = len(doc_tokens)
            self.doc_lengths.append(doc_len)
            total_len += doc_len

            # Count term frequencies in this document
            tf = Counter(doc_tokens)
            for term, freq in tf.items():
                self.inverted_index[term].append((doc_idx, freq))
                df[term] += 1

        self.avgdl = (total_len / self.corpus_size) if self.corpus_size > 0 else 0.0

        # Calculate IDFs
        # Standard BM25 IDF: ln((N - n + 0.5) / (n + 0.5) + 1.0)
        negative_idfs = []
        for term, freq in df.items():
            idf_val = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)
            self.idf[term] = idf_val
            if idf_val < 0:
                negative_idfs.append(term)

        # Handle negative IDFs with floor
        if negative_idfs:
            positive_idfs = [v for v in self.idf.values() if v > 0]
            avg_idf = sum(positive_idfs) / len(positive_idfs) if positive_idfs else 0.0
            eps = self.epsilon * avg_idf
            for term in negative_idfs:
                self.idf[term] = eps

        self.is_built = True
        logger.info(
            f"✅ [BM25] Index built successfully: {self.corpus_size} docs, "
            f"{len(self.idf)} unique terms, avgdl={self.avgdl:.1f}"
        )

    def search(
        self,
        query: str,
        top_k: int = 30,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search corpus using BM25 scoring.
        Returns top_k matching metadata dictionaries with '_score', '_rank', and '_bm25_score'.
        """
        if not self.is_built or not self.metadatas or not query:
            return []

        # Tokenize and stem query
        q_tokens = tokenize_for_retrieval(query, stem=True)
        # Filter out pure query stop words unless query only consists of stop words
        filtered_q = [t for t in q_tokens if t not in QUERY_STOP_WORDS]
        tokens_to_use = filtered_q if filtered_q else q_tokens

        if not tokens_to_use:
            return []

        # Accumulate BM25 scores for matching documents
        scores: Dict[int, float] = defaultdict(float)

        for term in tokens_to_use:
            if term not in self.inverted_index:
                continue

            term_idf = self.idf.get(term, 0.0)
            if term_idf <= 0:
                continue

            postings = self.inverted_index[term]
            for doc_idx, freq in postings:
                doc_len = self.doc_lengths[doc_idx]
                denom = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl if self.avgdl > 0 else 1.0))
                score_contrib = term_idf * (freq * (self.k1 + 1.0)) / (denom if denom > 0 else 1.0)
                scores[doc_idx] += score_contrib

        if not scores:
            return []

        # Filter and rank results
        ranked_doc_indices = sorted(scores.keys(), key=lambda idx: scores[idx], reverse=True)

        results: List[Dict[str, Any]] = []
        rank = 0
        for doc_idx in ranked_doc_indices:
            meta = self.metadatas[doc_idx]
            if filter_fn is not None and not filter_fn(meta):
                continue

            res = dict(meta)
            res["_faiss_index"] = doc_idx
            res["_score"] = float(scores[doc_idx])
            res["_bm25_score"] = float(scores[doc_idx])
            res["_rank"] = rank
            results.append(res)
            rank += 1

            if len(results) >= top_k:
                break

        return results
