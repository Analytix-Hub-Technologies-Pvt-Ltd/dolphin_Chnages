"""
Fuzzy Search Service

Provides intelligent fuzzy matching and suggestions when exact matches fail.
Helps users find content even with typos or incomplete terms.

GENERIC IMPLEMENTATION: Loads topics from actual database, not hardcoded list.
"""

from __future__ import annotations

from typing import List, Dict, Tuple, Optional, Any
from loguru import logger
import re


class FuzzySearchService:
    """
    Service for fuzzy matching query terms against database content.
    
    GENERIC FEATURES:
    - Loads ALL topics from actual database
    - Typo tolerance (Levenshtein distance)
    - Partial matching (SOL → SOLAS)
    - Automatic sync with database content
    - No hardcoded terms needed
    """
    
    def __init__(self, vector_store=None):
        """
        Initialize with optional vector store.
        
        Args:
            vector_store: FAISSStore instance for loading actual topics
        """
        self.vector_store = vector_store
        self.database_topics = []  # Topics loaded from actual database
        self.fallback_topics = {
            # Fallback maritime terms (only used if database load fails)
            "SOLAS": "International Convention for the Safety of Life at Sea",
            "MARPOL": "International Convention for the Prevention of Pollution from Ships",
            "STCW": "Standards of Training, Certification and Watchkeeping for Seafarers",
            "ISM": "International Safety Management Code",
            "SEEMP": "Ship Energy Efficiency Management Plan",
            "EEDI": "Energy Efficiency Design Index",
            "COLREG": "International Regulations for Preventing Collisions at Sea",
            "IMO": "International Maritime Organization",
        }
        logger.info(f"FuzzySearchService initialized (generic mode, vector_store={'present' if vector_store else 'absent'})")
    
    def load_topics_from_database(self) -> int:
        """
        Load all unique topics from the vector store for fuzzy matching.
        
        Returns:
            Number of topics loaded
        """
        if not self.vector_store:
            logger.warning("[FUZZY] No vector store provided, using fallback topics only")
            return 0
        
        try:
            # Get all topic names from vector store metadata
            topics = self.vector_store.get_all_topic_names()
            
            # Clean and deduplicate
            cleaned_topics = []
            for topic in topics:
                if isinstance(topic, str) and topic.strip():
                    cleaned_topics.append(topic.strip())
            
            self.database_topics = list(set(cleaned_topics))
            logger.info(f"[FUZZY] Loaded {len(self.database_topics)} unique topics from database")
            
            if len(self.database_topics) > 0:
                # Log sample topics
                sample = self.database_topics[:5]
                logger.info(f"[FUZZY] Sample topics: {sample}")
            
            return len(self.database_topics)
            
        except Exception as e:
            logger.error(f"[FUZZY] Failed to load topics from database: {e}")
            return 0
    
    def levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.
        Lower distance = more similar.
        """
        if len(s1) < len(s2):
            return self.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost of insertions, deletions, or substitutions
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def similarity_score(self, query: str, term: str) -> float:
        """
        Calculate similarity score (0.0 to 1.0, higher is more similar).
        
        Considers:
        - Levenshtein distance
        - Length ratio
        - Prefix matching
        """
        query_lower = query.lower().strip()
        term_lower = term.lower().strip()
        
        # Exact match
        if query_lower == term_lower:
            return 1.0
        
        # Prefix match (high score)
        if term_lower.startswith(query_lower):
            return 0.95
        
        # Calculate Levenshtein-based similarity
        max_len = max(len(query_lower), len(term_lower))
        if max_len == 0:
            return 0.0
        
        distance = self.levenshtein_distance(query_lower, term_lower)
        similarity = 1.0 - (distance / max_len)
        
        return max(0.0, similarity)
    
    def find_similar_terms(
        self, 
        query: str, 
        threshold: float = 0.6,
        max_results: int = 3
    ) -> List[Tuple[str, str, float]]:
        """
        Find similar terms to the query from ACTUAL database topics (generic!).
        
        Args:
            query: User's search term
            threshold: Minimum similarity score (0.0 to 1.0)
            max_results: Maximum number of suggestions
        
        Returns:
            List of (term, description, similarity_score) tuples
        """
        if not query or len(query) < 2:
            return []
        
        matches = []
        
        # PRIORITY 1: Search against actual database topics (GENERIC!)
        if self.database_topics:
            for topic in self.database_topics:
                score = self.similarity_score(query, topic)
                if score >= threshold:
                    # For database topics, description is empty (we don't need it)
                    matches.append((topic, "", score))
        
        # PRIORITY 2: Fallback to common maritime acronyms if database is empty
        if not matches and self.fallback_topics:
            for term, description in self.fallback_topics.items():
                score = self.similarity_score(query, term)
                if score >= threshold:
                    matches.append((term, description, score))
        
        # Sort by similarity score (descending)
        matches.sort(key=lambda x: x[2], reverse=True)
        
        return matches[:max_results]
    
    def suggest_corrections(
        self, 
        query: str,
        available_topics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate fuzzy match suggestions for a query.
        
        Args:
            query: User's original query
            available_topics: Optional list of topics from the database
        
        Returns:
            Dict with:
            - has_suggestions: bool
            - suggestions: List of dicts with 'term', 'description', 'confidence'
            - message: str (user-friendly message)
        """
        similar = self.find_similar_terms(query)
        
        if not similar:
            return {
                "has_suggestions": False,
                "suggestions": [],
                "message": f"I couldn't find any maritime topics similar to '{query}' in the course material."
            }
        
        # Format suggestions
        formatted_suggestions = []
        for term, description, score in similar:
            formatted_suggestions.append({
                "term": term,
                "description": description,
                "confidence": score,
                "display": f"{term} ({description})"
            })
        
        # Generate user message
        if len(similar) == 1:
            term = similar[0][0]
            message = f"Did you mean **{term}**?"
        else:
            terms = ", ".join([f"**{s[0]}**" for s in similar])
            message = f"Did you mean one of these: {terms}?"
        
        logger.info(f"[FUZZY] Query '{query}' → Found {len(similar)} similar terms")
        
        return {
            "has_suggestions": True,
            "suggestions": formatted_suggestions,
            "message": message
        }

    @staticmethod
    def _clean_topic_label(name: str) -> str:
        n = (name or "").strip()
        n = re.sub(r"^\s*\d+\s*[\.\)]\s*", "", n)
        n = re.sub(r"^(?:[A-Z]{2,6}-\d{2,6}-)+", "", n)
        n = re.sub(r"^\d+\.\s*", "", n)
        n = re.sub(r"\s+", " ", n).strip(" -:")
        return n

    COMMON_NON_MARITIME_WORDS = {
        "weather", "tokyo", "paris", "london", "india", "computer", "phone", "apple", "google",
        "today", "yesterday", "tomorrow", "time", "date", "year", "month", "week", "money",
        "food", "drink", "hotel", "flight", "car", "train", "bus", "movie", "music", "song",
        "game", "sport", "football", "cricket", "basketball", "tennis", "politics", "president",
        "minister", "doctor", "hospital", "medicine", "health", "school", "college", "university",
        "hello", "thanks", "goodbye", "please", "photo", "photosynthesis", "picture", "movie",
        "about", "would", "could", "should", "there", "their", "where", "which"
    }

    def _get_vocab(self, all_topic_names: Optional[List[str]] = None) -> set:
        topics = all_topic_names or self.database_topics
        if not topics and self.vector_store:
            try:
                topics = self.vector_store.get_all_topic_names()
            except Exception:
                topics = []
        if not topics:
            topics = list(self.fallback_topics.keys())
        
        vocab = set()
        for t in topics:
            cleaned = self._clean_topic_label(t)
            for word in re.findall(r'[A-Za-z0-9]{3,}', cleaned.lower()):
                vocab.add(word)
        for term in self.fallback_topics:
            vocab.add(term.lower())
        return vocab

    def detect_misspelled_query(
        self,
        query: str,
        all_topic_names: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if the user query contains a misspelled maritime term.
        If a typo is found, returns a dictionary with:
        - misspelled_word: str
        - corrected_term: str
        - related_topics: List[str] (up to 4 topics containing the corrected term)
        - message: str (friendly Did you mean... question)
        """
        if not query or not isinstance(query, str):
            return None

        q = query.strip()
        # Clean question prefixes
        q_clean = re.sub(r"^(?:what is|what are|tell me about|explain|meaning of|definition of|can you explain|how does|how do)\s+", "", q.lower()).strip()
        q_clean = re.sub(r"[^\w\s]", " ", q_clean).strip()
        tokens = [w for w in q_clean.split() if w and w not in {"the", "a", "an", "is", "are", "of", "in", "on", "for", "to", "and", "with"}]

        # Only evaluate concise queries (1 to 4 focus words) to prevent false positives on long paragraphs
        if not tokens or len(tokens) > 4:
            return None

        topics = all_topic_names or self.database_topics
        if not topics and self.vector_store:
            try:
                topics = self.vector_store.get_all_topic_names()
            except Exception:
                topics = []

        vocab = self._get_vocab(topics)

        # Skip if any token is already a known acronym or marine word
        for token in tokens:
            if token in vocab or token in self.COMMON_NON_MARITIME_WORDS or len(token) < 3:
                continue

            # Candidate misspelled word! Find best match in vocab
            best_match = None
            best_score = 0.0

            for v in vocab:
                if v in {"the", "and", "for", "with", "from", "some", "your", "what", "this", "that"}:
                    continue
                dist = self.levenshtein_distance(token, v)
                max_allowed = 1 if len(token) <= 6 else 2
                if dist <= max_allowed:
                    score = self.similarity_score(token, v)
                    if score > best_score and score >= 0.75:
                        best_score = score
                        best_match = v

            if best_match:
                # Find related topics in the curriculum that contain this corrected term
                related_topics = []
                seen_labels = set()
                term_lower = best_match.lower()

                for t in topics or self.database_topics:
                    cl = self._clean_topic_label(t)
                    if not cl or cl.lower() in seen_labels:
                        continue
                    if re.search(r'\b' + re.escape(term_lower) + r'\b', cl.lower()):
                        seen_labels.add(cl.lower())
                        related_topics.append(cl)

                # Fallback if no exact word boundary match in titles: substring search
                if not related_topics:
                    for t in topics or self.database_topics:
                        cl = self._clean_topic_label(t)
                        if not cl or cl.lower() in seen_labels:
                            continue
                        if term_lower in cl.lower():
                            seen_labels.add(cl.lower())
                            related_topics.append(cl)

                # Fallback if database had no direct title hits: use fallback description
                if not related_topics:
                    desc = self.fallback_topics.get(best_match.upper(), "")
                    if desc:
                        related_topics.append(f"{best_match.upper()} - {desc}")
                    else:
                        related_topics.append(f"Explain {best_match.title()} in maritime operations")

                # Format suggestions as natural, clickable questions
                suggestion_queries = []
                for rt in related_topics[:4]:
                    suggestion_queries.append(rt)

                formatted_term = best_match.upper() if len(best_match) <= 4 and best_match.upper() in self.fallback_topics else best_match.title()

                message = (
                    f"It looks like **\"{token}\"** might be a typo. "
                    f"Did you mean **{formatted_term}**?\n\n"
                    f"Here are related topics you can explore:"
                )

                logger.info(f"[FUZZY] Detected typo '{token}' -> '{formatted_term}' in '{query}' (score={best_score:.2f})")

                return {
                    "is_misspelled": True,
                    "misspelled_word": token,
                    "corrected_term": formatted_term,
                    "related_topics": suggestion_queries,
                    "message": message,
                }

        return None

