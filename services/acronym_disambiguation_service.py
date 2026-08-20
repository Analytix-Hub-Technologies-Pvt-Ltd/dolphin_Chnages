"""
Acronym Disambiguation Service

Detects and resolves ambiguous maritime acronyms to prevent returning wrong content.
Example: User types "EEDI" but system has both "EEDI" and "EEBD" - needs clarification.
"""

from __future__ import annotations

from typing import List, Dict, Optional, Tuple
from loguru import logger
import re


class AcronymDisambiguationService:
    """
    Service to detect and resolve ambiguous acronyms in maritime queries.
    
    Key Features:
    - Detects when user query matches multiple similar acronyms
    - Calculates acronym similarity (EEDI vs EEBD)
    - Generates clarification responses with options
    - Prevents returning wrong content for ambiguous terms
    """
    
    def __init__(self, vector_store=None):
        """
        Initialize with optional vector store for loading actual acronyms.
        
        Args:
            vector_store: FAISSStore instance for accessing indexed content
        """
        self.vector_store = vector_store
        self.known_acronyms: Dict[str, str] = {}  # acronym -> full name mapping
        logger.info("AcronymDisambiguationService initialized")
    
    def load_acronyms_from_database(self) -> int:
        """
        Load all acronyms from the vector store's indexed content.
        
        Returns:
            Number of acronyms loaded
        """
        if not self.vector_store:
            logger.warning("No vector store provided, using fallback acronyms only")
            return 0
        
        try:
            # Get all topics from vector store
            all_topics = self.vector_store.get_all_topic_names()
            
            # Extract acronyms (typically 2-6 uppercase letters)
            acronym_pattern = re.compile(r'\b([A-Z]{2,6})\b')
            
            for topic in all_topics:
                # Check if topic contains an acronym
                matches = acronym_pattern.findall(topic)
                for acronym in matches:
                    # Store acronym with its full context
                    if acronym not in self.known_acronyms:
                        self.known_acronyms[acronym] = topic
                    else:
                        # Multiple topics contain this acronym - mark as potentially ambiguous
                        existing = self.known_acronyms[acronym]
                        if topic != existing:
                            # Store both versions
                            self.known_acronyms[f"{acronym}_alt"] = topic
            
            logger.info(f"Loaded {len(self.known_acronyms)} acronyms from database")
            return len(self.known_acronyms)
            
        except Exception as e:
            logger.error(f"Failed to load acronyms from database: {e}")
            return 0
    
    def calculate_acronym_similarity(self, acronym1: str, acronym2: str) -> float:
        """
        Calculate similarity between two acronyms (0.0 to 1.0).
        
        High similarity examples:
        - EEDI vs EEBD: 0.75 (3 out of 4 letters match positions)
        - SOLAS vs STOLAS: 0.67
        
        Args:
            acronym1: First acronym
            acronym2: Second acronym
            
        Returns:
            Similarity score (0.0 = completely different, 1.0 = identical)
        """
        if acronym1 == acronym2:
            return 1.0
        
        # Normalize to uppercase
        a1 = acronym1.upper()
        a2 = acronym2.upper()
        
        # Check length similarity
        len_diff = abs(len(a1) - len(a2))
        if len_diff > 2:
            return 0.0  # Too different in length
        
        # Calculate character overlap at same positions
        min_len = min(len(a1), len(a2))
        matching_positions = sum(1 for i in range(min_len) if a1[i] == a2[i])
        
        # Also check for character set overlap (ignoring position)
        set1 = set(a1)
        set2 = set(a2)
        char_overlap = len(set1 & set2) / max(len(set1), len(set2))
        
        # Combined score
        position_score = matching_positions / max(len(a1), len(a2))
        final_score = (position_score * 0.7) + (char_overlap * 0.3)
        
        return final_score
    
    def find_similar_acronyms(
        self, 
        query_acronym: str, 
        similarity_threshold: float = 0.6
    ) -> List[Tuple[str, str, float]]:
        """
        Find acronyms similar to the query that might cause confusion.
        
        Args:
            query_acronym: The acronym user queried
            similarity_threshold: Minimum similarity to consider (0.0-1.0)
            
        Returns:
            List of (acronym, full_name, similarity_score) tuples, sorted by similarity
        """
        query_upper = query_acronym.upper()
        similar = []
        
        for acronym, full_name in self.known_acronyms.items():
            # Skip alternate entries
            if "_alt" in acronym:
                continue
            
            if acronym == query_upper:
                # Exact match - still include in case there are alternates
                similar.append((acronym, full_name, 1.0))
                continue
            
            similarity = self.calculate_acronym_similarity(query_upper, acronym)
            if similarity >= similarity_threshold:
                similar.append((acronym, full_name, similarity))
        
        # Sort by similarity (highest first)
        similar.sort(key=lambda x: x[2], reverse=True)
        
        return similar
    
    def is_ambiguous(
        self, 
        query: str,
        chunks: List[Dict],
        similarity_threshold: float = 0.7
    ) -> Tuple[bool, List[str]]:
        """
        Determine if a query is ambiguous based on:
        1. Multiple similar acronyms exist
        2. Retrieved chunks contain mixed acronyms
        
        Args:
            query: User query
            chunks: Retrieved chunks from vector search
            similarity_threshold: How similar acronyms need to be to cause confusion
            
        Returns:
            (is_ambiguous, list_of_possible_acronyms)
        """
        # Extract potential acronym from query
        query_clean = query.strip().upper()
        
        # Check if query is a single acronym (2-6 letters, all caps)
        if not re.match(r'^[A-Z]{2,6}$', query_clean):
            return False, []
        
        # Find similar acronyms
        similar_acronyms = self.find_similar_acronyms(query_clean, similarity_threshold)
        
        # If multiple similar acronyms found, it's ambiguous
        if len(similar_acronyms) > 1:
            acronym_list = [acr for acr, _, _ in similar_acronyms]
            logger.info(f"AMBIGUOUS: '{query}' matches {len(similar_acronyms)} acronyms: {acronym_list}")
            return True, acronym_list
        
        # Check chunks for mixed acronyms
        chunk_acronyms = set()
        for chunk in chunks[:5]:  # Check top 5 chunks
            content = chunk.get("content", "") or chunk.get("topic_name", "")
            if isinstance(content, str):
                # Extract acronyms from content
                found_acronyms = re.findall(r'\b([A-Z]{2,6})\b', content[:200])
                chunk_acronyms.update(found_acronyms)
        
        # Check if chunks contain similar but different acronyms
        conflicting_acronyms = []
        for chunk_acr in chunk_acronyms:
            similarity = self.calculate_acronym_similarity(query_clean, chunk_acr)
            if similarity >= similarity_threshold and chunk_acr != query_clean:
                conflicting_acronyms.append(chunk_acr)
        
        if conflicting_acronyms:
            logger.warning(f"AMBIGUOUS: Chunks for '{query}' contain similar acronyms: {conflicting_acronyms}")
            return True, [query_clean] + conflicting_acronyms
        
        return False, []
    
    def generate_clarification_prompt(
        self,
        query: str,
        possible_acronyms: List[str]
    ) -> str:
        """
        Generate a user-friendly clarification request when ambiguity is detected.
        
        Args:
            query: Original user query
            possible_acronyms: List of acronyms that might match
            
        Returns:
            Formatted clarification message
        """
        # Build options list
        options = []
        for i, acronym in enumerate(possible_acronyms[:4], 1):  # Max 4 options
            full_name = self.known_acronyms.get(acronym, "")
            if full_name:
                options.append(f"{i}. **{acronym}** - {full_name}")
            else:
                options.append(f"{i}. **{acronym}**")
        
        clarification = f"""I found multiple maritime acronyms similar to "{query}". 

Could you please clarify which one you're asking about?

{chr(10).join(options)}

Please let me know which topic interests you, or provide more context!"""
        
        return clarification
