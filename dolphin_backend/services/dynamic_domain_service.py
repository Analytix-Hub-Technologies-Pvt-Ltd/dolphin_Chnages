"""
services/dynamic_domain_service.py

Dynamic, self-learning maritime domain terminology service.
Harvests course topics, module names, and video titles from PostgreSQL into an ultra-fast,
in-memory normalized knowledge set.

Features:
1. Zero Manual Maintenance: Automatically learns all topic titles, lessons, and video titles
   from PostgreSQL at startup (or on demand).
2. 0.00ms In-Memory Fast-Path: O(1) set lookups for full queries and multi-word n-grams.
3. Safe & Additive: Sits behind existing static lists as an automated extension.
   Cannot crash the server or disrupt existing chat workflows.
"""

from typing import Set, Optional, Tuple
import asyncio
import re
import time
from loguru import logger

STOP_WORDS: Set[str] = {
    "the", "and", "for", "not", "all", "new", "topic", "part", "types", "type",
    "basic", "how", "why", "what", "with", "from", "into", "over", "under",
    "after", "before", "some", "many", "most", "page", "unit", "level", "stage",
    "class", "grade", "rule", "rules", "case", "cases", "can", "you", "your",
    "our", "who", "whom", "which", "that", "this", "these", "those", "yes",
    "please", "tell", "give", "show", "list", "view", "test", "user", "role",
    "about", "between", "through", "during", "without", "again", "further", "then",
    "once", "here", "there", "when", "where", "both", "each", "few", "more", "other",
    "such", "no", "nor", "too", "very", "only", "own", "same", "so", "than",
    "s", "t", "will", "just", "don", "should", "now", "helps", "methods",
    "operation", "components", "introduction", "overview", "summary", "conclusion",
    "part 1", "part 2", "part 3", "part 4", "guide", "simple", "to", "in", "on", "at",
    "by", "an", "a", "as", "of", "off", "do", "does", "did", "doing", "be", "is", "are",
    "was", "were", "been", "being", "have", "has", "had", "having", "its", "it",
    "would", "could", "may", "might", "must", "shall", "out", "up", "down"
}


class DynamicDomainService:
    def __init__(self) -> None:
        self._exact_topics: Set[str] = set()
        self._topic_ngrams: Set[str] = set()
        self._initialized: bool = False
        self._lock = asyncio.Lock()

    def _clean_text(self, text: str) -> str:
        """Strip punctuation and normalize whitespace."""
        t = re.sub(r'[^a-zA-Z0-9\s]', ' ', text).lower()
        return re.sub(r'\s+', ' ', t).strip()

    def _singularize(self, word: str) -> str:
        """Singularize plural English nouns."""
        if word.endswith('ies') and len(word) > 4:
            return word[:-3] + 'y'
        if word.endswith('es') and len(word) > 4:
            return word[:-2]
        if word.endswith('s') and len(word) > 3:
            return word[:-1]
        return word

    def _singularize_phrase(self, phrase: str) -> str:
        """Singularize the final word in a multi-word phrase."""
        words = phrase.split()
        if not words:
            return ""
        words[-1] = self._singularize(words[-1])
        return " ".join(words)

    async def harvest_course_topics(self, pool=None) -> int:
        """
        Scans distinct course_content topic names and transcribe video titles from PostgreSQL.
        Builds in-memory exact topics and n-grams in ~0.5s.
        """
        if self._initialized:
            return len(self._exact_topics) + len(self._topic_ngrams)

        async with self._lock:
            if self._initialized:
                return len(self._exact_topics) + len(self._topic_ngrams)

            t0 = time.perf_counter()
            try:
                if pool is None:
                    from models.database import get_pool
                    pool = await get_pool()

                topic_rows = await pool.fetch(
                    "SELECT DISTINCT topic_name FROM course_content WHERE topic_name IS NOT NULL"
                )
                video_rows = await pool.fetch(
                    "SELECT DISTINCT video_title FROM transcribe WHERE video_title IS NOT NULL"
                )
            except Exception as e:
                logger.warning(f"⚠️ [Dynamic Domain] DB harvesting skipped (DB unavailable): {e}")
                return 0

            all_titles = [r["topic_name"] for r in topic_rows if r.get("topic_name")] + [
                r["video_title"] for r in video_rows if r.get("video_title")
            ]

            exact_set: Set[str] = set()
            ngram_set: Set[str] = set()

            for raw in all_titles:
                if not raw:
                    continue
                # Split clauses by punctuation delimiters
                sub_clauses = re.split(r'[-:—()/,|]', raw)
                for clause in sub_clauses:
                    cl = self._clean_text(clause)
                    words = cl.split()
                    while words and words[0] in STOP_WORDS:
                        words.pop(0)
                    while words and words[-1] in STOP_WORDS:
                        words.pop()

                    if len(words) >= 2:
                        phrase = " ".join(words)
                        exact_set.add(phrase)
                        exact_set.add(self._singularize_phrase(phrase))

                        # Build 2-word, 3-word, and 4-word n-grams
                        for n in (2, 3, 4):
                            for i in range(len(words) - n + 1):
                                sub = words[i:i + n]
                                if sub[0] not in STOP_WORDS and sub[-1] not in STOP_WORDS:
                                    sub_str = " ".join(sub)
                                    ngram_set.add(sub_str)
                                    ngram_set.add(self._singularize_phrase(sub_str))

            self._exact_topics = exact_set
            self._topic_ngrams = ngram_set
            self._initialized = True

            dur = time.perf_counter() - t0
            logger.success(
                f"🌊 [Dynamic Domain] Harvested {len(self._exact_topics)} topics and "
                f"{len(self._topic_ngrams)} n-grams from {len(all_titles)} titles in {dur:.2f}s"
            )
            return len(self._exact_topics) + len(self._topic_ngrams)

    def is_db_domain_match(self, query: str) -> bool:
        """
        Ultra-fast O(1) in-memory check to see if a query matches any database course topic or n-gram.
        Returns True if query matches, False otherwise (takes < 0.05ms).
        """
        if not self._initialized or not query or not isinstance(query, str):
            return False

        q_clean = self._clean_text(query)
        q_clean = re.sub(r'backzone\b', 'back zone', q_clean)
        words = q_clean.split()
        if not words:
            return False

        # 1. Full phrase check
        q_sing = self._singularize_phrase(q_clean)
        if q_clean in self._exact_topics or q_sing in self._exact_topics:
            return True

        # 2. Query n-grams check (length 4 down to 2)
        for n in (4, 3, 2):
            for i in range(len(words) - n + 1):
                sub = words[i:i + n]
                if sub[0] not in STOP_WORDS and sub[-1] not in STOP_WORDS:
                    sub_str = " ".join(sub)
                    sub_sing = self._singularize_phrase(sub_str)
                    if sub_str in self._exact_topics or sub_sing in self._exact_topics:
                        return True
                    if sub_str in self._topic_ngrams or sub_sing in self._topic_ngrams:
                        return True

        # 3. Additive check: Technical framework/model compound queries (e.g., "ABC Model", "SHELL Model", "Bow Tie Concept")
        TECHNICAL_FRAMEWORK_SUFFIXES = {
            "model", "models", "theory", "theories", "framework", "frameworks",
            "matrix", "diagram", "diagrams", "concept", "concepts", "principle", "principles"
        }
        clean_words = [w for w in words if w not in STOP_WORDS]
        if any(w in TECHNICAL_FRAMEWORK_SUFFIXES for w in clean_words) and len(clean_words) >= 2:
            core_words = [w for w in clean_words if w not in TECHNICAL_FRAMEWORK_SUFFIXES]
            if core_words:
                core_phrase = " ".join(core_words)
                core_sing = self._singularize_phrase(core_phrase)
                if (
                    core_phrase in self._exact_topics 
                    or core_sing in self._exact_topics
                    or core_phrase in self._topic_ngrams
                    or core_sing in self._topic_ngrams
                ):
                    return True
                try:
                    from services.maritime_acronyms import is_known_maritime_acronym
                    if any(is_known_maritime_acronym(w.upper()) for w in core_words):
                        return True
                except Exception:
                    pass

        return False

    def clear_cache(self) -> None:
        """Reset harvested cache for hot reload."""
        self._exact_topics.clear()
        self._topic_ngrams.clear()
        self._initialized = False


# Singleton export
dynamic_domain_service = DynamicDomainService()
