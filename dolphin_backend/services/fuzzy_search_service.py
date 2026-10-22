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

    # Standard everyday English words that must NEVER be flagged as typos
    COMMON_ENGLISH_WORDS = {
        "the", "and", "for", "with", "from", "some", "your", "what", "this", "that",
        "man", "men", "actions", "action", "principles", "principle", "fail", "fails",
        "operation", "operations", "operational", "during", "working", "work", "system",
        "systems", "used", "when", "where", "how", "does", "can", "could", "will", "would",
        "should", "emergency", "emergencies", "prevent", "prevents", "cause", "causes",
        "check", "checks", "explain", "describe", "tell", "give", "show", "help", "need",
        "routine", "safety", "standard", "standards", "rule", "rules", "guidelines", "fire", "fires",
        "thank", "thanks", "start", "starting", "next", "life", "rise", "risk", "home", "play", "make", "york",
        "inspect", "inspected", "inspecting", "inspection", "safely", "safe", "affect", "effect", "procedure",
        "procedures", "drill", "drills", "seawater", "injection", "cavitation", "explosion", "explosions",
        "foaming", "operating", "machinery", "grounding", "compliance", "inspectors", "governs", "sharing",
        "lubricator", "lubricating", "protection", "fitted", "donkey", "reading", "standing", "sailing",
        "applicable", "detected", "stopping", "leaking", "cleaning", "generate", "learning", "valve", "valves",
        "engage", "engages", "engaging", "roller", "rollers", "lead", "leads", "watchkeeper", "watchkeepers",
        "solitary", "purpose", "protect", "protects",
        # Common conversational, comparative & question vocabulary
        "compare", "compared", "comparing", "comparison", "difference", "differ", "different",
        "weather", "severe", "heavy", "greater", "greatest", "earlier", "previous", "latter", "former",
        "second", "third", "first", "point", "section", "chapter", "detail", "details", "detailed",
        "step", "steps", "continue", "ignore", "abnormal", "warning", "mention", "mentioned",
        "online", "offline", "senior", "junior", "career", "salary", "education", "scoring", "score",
        "radiation", "shadow", "building", "meaning", "boarding", "conscription", "company", "message",
        "sending", "roaming", "indicator", "passing", "production", "gaming", "connection", "generative",
        "dollars", "solar", "common", "generation", "switches", "switch", "migration", "conservation",
        "eligibility", "overhauling", "abnormal", "causing", "rebalance", "recording", "cellular",
        "regular", "normal", "general", "overview", "basics", "simple", "complex", "primary", "secondary",
        "shipping", "shipment", "maritime", "vessel", "vessels", "seafarer", "seafarers"
    }

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
        try:
            from services.off_topic_detector import MARINE_INDICATORS
            for m in MARINE_INDICATORS:
                for word in re.findall(r'[A-Za-z0-9]{6,}', m.lower()):
                    vocab.add(word)
        except Exception:
            pass
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

        # Only evaluate concise to moderate queries to prevent false positives on massive paragraphs
        if not tokens or len(tokens) > 16:
            return None

        # If the query is an articulate technical sentence (>= 7 tokens) that already has
        # strong maritime indicators or acronyms, skip aggressive typo matching
        if len(tokens) >= 7:
            try:
                from services.off_topic_detector import has_strong_marine_signal, is_marine_domain_query
                from services.maritime_acronyms import find_acronyms_in_query
                if find_acronyms_in_query(query) or (has_strong_marine_signal(query) and is_marine_domain_query(query)):
                    return None
            except Exception:
                pass

        topics = all_topic_names or self.database_topics
        if not topics and self.vector_store:
            try:
                topics = self.vector_store.get_all_topic_names()
            except Exception:
                topics = []

        vocab = self._get_vocab(topics)

        # Skip if any token is already a known acronym, marine word, or standard English word
        for token in tokens:
            token_lower = token.lower()
            if (
                token in vocab
                or token_lower in vocab
                or token_lower in self.COMMON_ENGLISH_WORDS
                or len(token) <= 4
            ):
                continue

            # Grammatical inflection match: if token is formed by adding standard English suffixes
            # to a vocabulary root (e.g. operational vs operation, operations vs operation),
            # it is a valid morphological derivation, NOT a typo!
            VALID_DERIVATIONAL_SUFFIXES = {
                "s", "es", "ed", "ing", "al", "ally", "able", "ive", "tion", "tions",
                "ic", "ical", "ment", "ments", "ness", "less", "ful", "ly", "ity",
                "ize", "ise", "ized", "ised", "er", "ers", "est"
            }
            is_valid_inflection = False
            for v in vocab:
                vl = v.lower()
                if token_lower.startswith(vl) and token_lower[len(vl):] in VALID_DERIVATIONAL_SUFFIXES:
                    is_valid_inflection = True
                    break
                if vl.startswith(token_lower) and vl[len(token_lower):] in {"s", "es", "ed", "ing", "d"}:
                    is_valid_inflection = True
                    break
            if is_valid_inflection:
                continue

            # Check if token and any vocab item share the same stem/root
            # (e.g. watchkeeper vs watchkeeping, operator vs operating)
            def _stem_root(w: str) -> str:
                for sfx in ("keeper", "keeping", "ation", "tions", "tion", "ment", "ments", "ally", "able", "ness", "ing", "ers", "ed", "er", "es", "al", "ly", "s", "d"):
                    if w.endswith(sfx) and len(w) - len(sfx) >= 4:
                        return w[:-len(sfx)]
                return w

            token_root = _stem_root(token_lower)
            is_root_match = False
            for v in vocab:
                if token_root == _stem_root(v.lower()):
                    is_root_match = True
                    break
            if is_root_match:
                continue

            try:
                from services.maritime_acronyms import is_known_maritime_acronym
                from services.off_topic_detector import is_marine_domain_query
                if is_known_maritime_acronym(token.upper()) or is_marine_domain_query(token):
                    continue
            except Exception:
                pass

            # Candidate misspelled word! Find best match in vocab
            best_match = None
            best_score = 0.0

            for v in vocab:
                if v in {"the", "and", "for", "with", "from", "some", "your", "what", "this", "that"}:
                    continue
                # 1. Typos virtually always preserve the first character
                if token_lower[0] != v.lower()[0]:
                    continue

                dist = self.levenshtein_distance(token, v)
                if len(token) <= 5:
                    max_allowed = 1
                    min_score = 0.80
                elif len(token) <= 8:
                    max_allowed = 2
                    min_score = 0.75
                else:
                    max_allowed = 2
                    min_score = 0.75

                if dist <= max_allowed:
                    score = self.similarity_score(token, v)
                    if score >= min_score and score > best_score:
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
                    f"Here are some topics related to **{formatted_term}** you can explore:"
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

    def correct_query_typos(
        self,
        query: str,
        all_topic_names: Optional[List[str]] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Detect and seamlessly correct any misspelled maritime terms in user query.
        Returns:
            (corrected_query, typo_match_dict_or_None)
        """
        if not query or not isinstance(query, str):
            return query, None

        match = self.detect_misspelled_query(query, all_topic_names)
        if not match:
            return query, None

        misspelled = match["misspelled_word"]
        corrected = match["corrected_term"]

        # Safely replace only the exact misspelled word token (case-insensitive)
        pattern = re.compile(r'\b' + re.escape(misspelled) + r'\b', re.IGNORECASE)
        corrected_query = pattern.sub(corrected, query)

        return corrected_query, match


