import math
import os
import pickle
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set
from loguru import logger

BM25_CACHE_PATH = os.path.join(os.path.dirname(__file__), "faiss_index.bm25.pkl")


def tokenize(text: str) -> List[str]:
    """
    Maritime & technical domain aware tokenizer.
    Extracts words, alphanumeric terms, codes (e.g., SOLAS, CP005, COW, MARPOL, Annex I, 1978).
    """
    if not text or not isinstance(text, str):
        return []
    # Normalize and extract terms
    tokens = re.findall(r"\b[a-zA-Z0-9_\-\.\/]{2,}\b", text.lower())
    return tokens


class BM25Store:
    """
    In-memory BM25Okapi search engine for exact keyword retrieval.
    Designed for fast sparse keyword retrieval alongside FAISS dense vector search.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size: int = 0
        self.avg_doc_len: float = 0.0
        self.doc_lens: List[int] = []
        self.doc_freqs: Dict[str, int] = defaultdict(int)
        self.idf: Dict[str, float] = {}
        self.inverted_index: Dict[str, List[tuple[int, int]]] = defaultdict(list)  # term -> list of (doc_idx, term_freq)
        self.documents: List[Dict[str, Any]] = []
        self.is_indexed: bool = False

    def save_cache(self, path: str = BM25_CACHE_PATH) -> bool:
        """Serialize the built BM25 index to disk for fast startup."""
        try:
            state = {
                "corpus_size": self.corpus_size,
                "avg_doc_len": self.avg_doc_len,
                "doc_lens": self.doc_lens,
                "doc_freqs": dict(self.doc_freqs),
                "idf": self.idf,
                "inverted_index": dict(self.inverted_index),
                "documents": self.documents,
                "is_indexed": self.is_indexed,
            }
            with open(path, "wb") as f:
                pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info(f"💾 Saved BM25 cache to {path} ({self.corpus_size} docs)")
            return True
        except Exception as e:
            logger.warning(f"Failed to save BM25 cache: {e}")
            return False

    def load_cache(self, path: str = BM25_CACHE_PATH) -> bool:
        """Load pre-built BM25 index from disk cache."""
        if not os.path.exists(path):
            return False
        try:
            logger.info(f"📦 Loading BM25 cache from {path}...")
            with open(path, "rb") as f:
                state = pickle.load(f)
            self.corpus_size = state.get("corpus_size", 0)
            self.avg_doc_len = state.get("avg_doc_len", 0.0)
            self.doc_lens = state.get("doc_lens", [])
            self.doc_freqs = defaultdict(int, state.get("doc_freqs", {}))
            self.idf = state.get("idf", {})
            self.inverted_index = defaultdict(list, state.get("inverted_index", {}))
            self.documents = state.get("documents", [])
            self.is_indexed = state.get("is_indexed", True)
            logger.success(f"✅ Loaded BM25 cache from disk: {self.corpus_size} docs, {len(self.idf)} terms")
            return True
        except Exception as e:
            logger.warning(f"Failed to load BM25 cache from {path}: {e}")
            return False

    def build_index(self, documents: List[Dict[str, Any]]) -> None:
        """
        Build the BM25 index from a list of document metadata dictionaries.
        Each dictionary should contain 'content', 'topic_name', and/or 'title'.
        """
        if not documents:
            logger.warning("BM25Store.build_index(): empty documents passed")
            self.reset()
            return

        logger.info(f"🏗️ Building BM25 index for {len(documents)} documents...")
        self.documents = list(documents)
        self.corpus_size = len(documents)
        self.doc_lens = []
        self.doc_freqs = defaultdict(int)
        self.inverted_index = defaultdict(list)

        total_len = 0

        for idx, doc in enumerate(documents):
            # Combine topic name (boosted weight) and content
            topic = doc.get("topic_name") or doc.get("title") or ""
            content = doc.get("content") or doc.get("topic_content") or doc.get("text") or doc.get("page_content") or ""
            text = f"{topic} {topic} {content}".strip()
            if not text:
                text = " ".join(str(v) for v in doc.values() if isinstance(v, str))

            tokens = tokenize(text)
            doc_len = len(tokens)
            self.doc_lens.append(doc_len)
            total_len += doc_len

            term_counts = Counter(tokens)
            for term, count in term_counts.items():
                self.doc_freqs[term] += 1
                self.inverted_index[term].append((idx, count))

        self.avg_doc_len = (total_len / self.corpus_size) if self.corpus_size > 0 else 0.0

        # Calculate IDF for all terms
        self.idf = {}
        for term, df in self.doc_freqs.items():
            # BM25 Okapi IDF formula with +1 for smooth floor
            idf_val = math.log(1.0 + (self.corpus_size - df + 0.5) / (df + 0.5))
            self.idf[term] = max(0.01, idf_val)

        self.is_indexed = True
        logger.success(
            f"✅ BM25 index built: {self.corpus_size} docs, {len(self.idf)} unique terms, avg_len={self.avg_doc_len:.1f}"
        )

    def reset(self) -> None:
        """Clear the BM25 index."""
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_lens = []
        self.doc_freqs = defaultdict(int)
        self.idf = {}
        self.inverted_index = defaultdict(list)
        self.documents = []
        self.is_indexed = False

    def search(self, query: str, k: int = 10, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Execute BM25 exact keyword search for query string.
        Returns top-k documents sorted by BM25 score.
        """
        limit = top_k if top_k is not None else k
        if not self.is_indexed or self.corpus_size == 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        # Expand search terms to match bidirectional singular and plural variants seamlessly
        search_terms: Dict[str, float] = {}  # term -> weight multiplier
        for term in query_tokens:
            search_terms[term] = 1.0
            # Generate stemming variants (e.g. pumps <-> pump, boilers <-> boiler, etc.)
            if len(term) >= 4:
                if term.endswith("ies") and len(term) > 4:
                    search_terms.setdefault(term[:-3] + "y", 0.90)
                elif term.endswith("es") and len(term) > 4:
                    search_terms.setdefault(term[:-2], 0.90)
                    search_terms.setdefault(term[:-1], 0.90)
                elif term.endswith("s") and len(term) > 3:
                    search_terms.setdefault(term[:-1], 0.90)
                else:
                    search_terms.setdefault(term + "s", 0.90)

        scores: Dict[int, float] = defaultdict(float)

        for term, weight in search_terms.items():
            if term not in self.inverted_index:
                continue

            idf_val = self.idf.get(term, 0.0)
            postings = self.inverted_index[term]

            for doc_idx, tf in postings:
                doc_len = self.doc_lens[doc_idx]
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                term_score = idf_val * (numerator / denominator) * weight
                scores[doc_idx] += term_score

        if not scores:
            return []

        # Sort candidate indices by score descending
        sorted_indices = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]

        results: List[Dict[str, Any]] = []
        for rank, (doc_idx, score) in enumerate(sorted_indices):
            doc = dict(self.documents[doc_idx])
            doc["_bm25_score"] = float(score)
            doc["_bm25_rank"] = int(rank)
            results.append(doc)

        logger.debug(f"🔍 BM25 search for '{query}' returned {len(results)} matches")
        return results
