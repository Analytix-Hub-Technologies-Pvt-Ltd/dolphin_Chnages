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
