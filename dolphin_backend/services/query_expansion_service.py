"""
Query Expansion Service

Enhances user queries with maritime context, synonyms, and related terms
to improve semantic search retrieval quality.

GENERIC APPROACH: No hardcoded acronyms!
- Loads acronyms dynamically from database content
- Uses LLM for intelligent expansion of ANY query
- Works for future content without code changes
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from loguru import logger
from services.openai_service import OpenAIService


QUERY_EXPANSION_PROMPT = """You are a maritime education search query optimizer. Your task is to expand user queries to improve semantic search results in a maritime course database.

ORIGINAL QUERY: {query}

CHAT CONTEXT (last 3 exchanges):
{context}

TASK: Expand this query with:
1. Maritime terminology and full forms of acronyms
2. Related technical terms and synonyms
3. Common phrases used in maritime education
4. Context from chat history if relevant

RULES:
- Keep expansion concise (max 20-25 words)
- Focus on keywords, not full sentences
- Include both technical and common terms
- Maintain the original query's intent
- Add maritime domain context

EXAMPLES:

Original: "SEEMP"
Expanded: "SEEMP Ship Energy Efficiency Management Plan energy efficiency vessel operations fuel consumption"

Original: "EEDI"
Expanded: "EEDI Energy Efficiency Design Index ship design efficiency emissions CO2 MARPOL environmental regulations"

Original: "fire safety"
Expanded: "fire safety maritime firefighting procedures vessel fire prevention equipment suppression systems regulations"

Original: "stability"
Expanded: "ship stability vessel stability principles metacentric height center gravity buoyancy stability calculations"

Original: "navigation systems"
Expanded: "navigation systems GPS ECDIS radar AIS chart plotting electronic navigation marine navigation equipment"

Original: "cargo handling"
Expanded: "cargo handling loading unloading cargo operations stowage securing lashing cargo safety procedures"

Original: "cargo sampling"
Expanded: "cargo sampling procedures sampling methods cargo quality testing sample collection cargo inspection"

NOW EXPAND: {query}

EXPANDED QUERY (keywords only, concise):"""


class QueryExpansionService:
    """
    Service for expanding user queries to improve search retrieval.
    
    GENERIC APPROACH:
    - Uses LLM to expand ANY query (no hardcoded lists)
    - Dynamically loads acronyms from actual database content
    - Works for future acronyms without code changes
    
    Features:
    - Maritime acronym expansion (via database + LLM)
    - LLM-based semantic expansion
    - Context-aware enhancements
    - Caching for common queries
    """
    
    def __init__(self, openai_service: OpenAIService, vector_store=None, enabled: bool = True):
        self.openai_service = openai_service
        self.vector_store = vector_store
        self.enabled = enabled
        self._cache: Dict[str, str] = {}
        
        # Generic: Load acronyms dynamically from database
        self.known_acronyms: Dict[str, str] = {}
        if vector_store:
            self._load_acronyms_from_database()
        
        logger.info(
            f"QueryExpansionService initialized (enabled={enabled}, "
            f"database_acronyms={len(self.known_acronyms)})"
        )
    
    def _load_acronyms_from_database(self) -> None:
        """
        GENERIC: Load acronyms dynamically from vector store metadata.
        No hardcoded lists!
        """
        try:
            if not self.vector_store:
                return
            
            # Get all topics from the database
            all_topics = self.vector_store.get_all_topic_names()
            
            import re
            # Pattern: Look for acronyms in topics (2-6 uppercase letters)
            acronym_pattern = re.compile(r'\b([A-Z]{2,6})\b')
            
            for topic in all_topics:
                # Find acronyms in the topic name
                matches = acronym_pattern.findall(topic)
                for acronym in matches:
                    # Store acronym with its context (the full topic name)
                    if acronym not in self.known_acronyms:
                        self.known_acronyms[acronym] = topic
            
            logger.info(f"[EXPANSION] Loaded {len(self.known_acronyms)} acronyms from database")
            
        except Exception as e:
            logger.warning(f"[EXPANSION] Failed to load acronyms from database: {e}")
            logger.info("[EXPANSION] Will rely on LLM-only expansion")
    
    async def expand_query(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        use_llm: bool = True
    ) -> str:
        """
        Expand a user query to improve search results.
        
        Args:
            query: Original user query
            chat_history: Recent chat messages for context
            use_llm: Whether to use LLM expansion (fallback to rule-based if False)
        
        Returns:
            Expanded query string
        """
        if not self.enabled:
            return query
        
        if not query or not query.strip():
            return query
        
        original_query = query.strip()
        
        # Check cache first
        cache_key = original_query.lower()
        if cache_key in self._cache:
            logger.debug(f"[EXPANSION] Cache hit for: {original_query}")
            return self._cache[cache_key]
        
        # NEW: Skip LLM expansion for clear, detailed multi-word queries
        # These are already specific enough and don't benefit from expansion
        # Expansion can introduce non-determinism and hurt consistency
        if self._is_detailed_query(original_query):
            logger.info(f"[EXPANSION] Query is already detailed, skipping LLM expansion: '{original_query}'")
            self._cache[cache_key] = original_query
            return original_query
        
        # Step 1: Quick rule-based expansion for known acronyms
        expanded = self._expand_acronyms(original_query)
        
        # Step 2: LLM-based semantic expansion (if enabled and query is non-trivial)
        if use_llm and len(original_query.split()) <= 10:  # Only expand short queries
            try:
                expanded = await self._llm_expand(expanded, chat_history)
            except Exception as e:
                logger.warning(f"[EXPANSION] LLM expansion failed, using rule-based: {e}")
        
        # Cache the result
        self._cache[cache_key] = expanded
        
        # Limit cache size
        if len(self._cache) > 1000:
            # Remove oldest 200 entries
            for key in list(self._cache.keys())[:200]:
                del self._cache[key]
        
        logger.info(f"[EXPANSION] '{original_query}' → '{expanded}'")
        return expanded
    
    def _is_detailed_query(self, query: str) -> bool:
        """
        Check if a query is already detailed/specific enough that it doesn't need LLM expansion.
        
        Detailed queries are:
        - 3+ meaningful words (not just stop words)
        - Contains specific technical terms
        - Already descriptive enough for semantic search
        
        Examples of detailed queries (skip expansion):
        - "psychological tools for conflict management" (5 words, very specific)
        - "fire prevention and firefighting procedures" (5 words, clear)
        - "cargo sampling methods" (3 words, technical)
        
        Examples of simple queries (needs expansion):
        - "FPFF" (acronym - expand it)
        - "fire safety" (2 words - add context)
        - "stability" (1 word - too vague)
        
        Returns:
            True if query is detailed enough (skip LLM expansion)
        """
        query = query.strip()
        words = query.lower().split()
        
        # Filter out stop words to count meaningful words
        stop_words = {'the', 'a', 'an', 'for', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'with'}
        meaningful_words = [w for w in words if w not in stop_words and len(w) >= 3]
        
        # Criteria for "detailed": 3+ meaningful words
        # This covers phrases like "psychological tools conflict management" (4 words)
        if len(meaningful_words) >= 3:
            logger.debug(f"[EXPANSION] Query has {len(meaningful_words)} meaningful words, considered detailed")
            return True
        
        # Criteria 2: 4+ total words (even with some stop words)
        # This covers "tools for conflict management" (4 words, but "for" is stop word)
        if len(words) >= 4:
            logger.debug(f"[EXPANSION] Query has {len(words)} total words, considered detailed")
            return True
        
        # Not detailed - needs expansion
        return False
    
    def _expand_acronyms(self, query: str) -> str:
        """
        GENERIC: Expand acronyms using dynamically loaded database content.
        No hardcoded mappings!
        """
        query_upper = query.upper().strip()
        
        # Check if query is a single acronym (2-6 uppercase letters)
        if not (2 <= len(query_upper) <= 6 and query_upper.isalpha()):
            logger.debug(f"[EXPANSION] '{query}' not a simple acronym pattern, skipping rule-based")
            return query
        
        # Debug: Log search attempt
        logger.info(f"[EXPANSION] Looking for acronym '{query_upper}' in {len(self.known_acronyms)} loaded acronyms")
        
        # Look up in dynamically loaded acronyms from database
        if query_upper in self.known_acronyms:
            expansion = self.known_acronyms[query_upper]
            logger.info(f"[EXPANSION] Acronym found in database: {query_upper} → {expansion}")
            return f"{query_upper} {expansion}"
        
        # Debug: Show similar acronyms if not found
        similar = [k for k in self.known_acronyms.keys() if query_upper in k or k in query_upper]
        if similar:
            logger.warning(f"[EXPANSION] '{query_upper}' not found, but similar exist: {similar[:5]}")
        else:
            logger.warning(f"[EXPANSION] '{query_upper}' not found in database acronyms")
        
        # If not in database, return original (LLM will handle it)
        return query
    
    async def _llm_expand(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Use LLM to semantically expand the query with maritime context.
        """
        # Build context from chat history
        context_str = "No recent context"
        if chat_history:
            recent = chat_history[-3:]  # Last 3 messages
            context_parts = []
            for msg in recent:
                role = msg.get("role", "")
                content = str(msg.get("content", ""))[:150]  # Truncate long messages
                if role and content:
                    context_parts.append(f"{role}: {content}")
            if context_parts:
                context_str = "\n".join(context_parts)
        
        # Format prompt
        prompt = QUERY_EXPANSION_PROMPT.format(
            query=query,
            context=context_str
        )
        
        # Call LLM with temperature=0 for DETERMINISTIC results
        # CRITICAL: Same query must ALWAYS get same expansion → same chunks → same answer
        response = await self.openai_service.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,  # DETERMINISTIC: Ensures consistency across identical queries
            category="QUERY_EXPANSION"
        )
        
        expanded = response.strip()
        
        # Validation: Don't use expansion if it's too long or empty
        if not expanded or len(expanded) > 200:
            logger.warning(f"[EXPANSION] LLM returned invalid expansion, using original")
            return query
        
        return expanded
    
    def clear_cache(self) -> None:
        """Clear the expansion cache."""
        self._cache.clear()
        logger.info("[EXPANSION] Cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": 1000
        }
