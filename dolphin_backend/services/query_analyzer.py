from __future__ import annotations

import re
import string
import difflib
from typing import Dict, List, Tuple
from loguru import logger
from services.gpt_intent_service import GPTIntentService
from services.off_topic_detector import (
    is_off_topic_query,
    is_marine_domain_query,
    is_obvious_marine_query,
)


def extract_name(text: str) -> str | None:
    """Extract user's name from greeting sentences."""
    text = text.lower()

    patterns = [
        r"i am ([a-zA-Z]+)",
        r"i'm ([a-zA-Z]+)",
        r"this is ([a-zA-Z]+)",
        r"my name is ([a-zA-Z]+)",
    ]

    for p in patterns:
        match = re.search(p, text)
        if match:
            return match.group(1).title()

    return None


def is_greeting_query(query: str) -> bool:
    """
    Fast, reliable check if a query is purely a greeting or introduction.
    Avoids expensive LLM query rewrites, intent classifications, and vector searches.
    """
    if not query or not isinstance(query, str):
        return False

    q = query.strip()
    if not q:
        return False

    # Normalize: remove punctuation, lower-case
    cleaned = re.sub(r"[^\w\s]", " ", q.lower()).strip()
    words = cleaned.split()
    if not words:
        return False

    # Common vocabulary used in greetings / salutations / polite introductions
    GREETING_WORDS = {
        "hi", "hello", "hey", "yo", "hola", "howdy", "greetings", "greet",
        "good", "morning", "afternoon", "evening", "day", "night",
        "there", "dolphin", "assistant", "ai", "bot", "buddy", "friend",
        "sir", "maam", "team", "all", "everyone", "marine", "tutor",
        "i", "am", "im", "my", "name", "is", "this", "welcome", "dear"
    }

    # If all words in the input belong to greeting vocabulary (up to 7 words)
    if len(words) <= 7 and all(w in GREETING_WORDS for w in words):
        return True

    # Exact common greeting phrases
    EXACT_GREETINGS = {
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "good day", "greetings", "howdy", "hola", "yo", "hi there", "hello there",
        "hey there", "hello dolphin", "hi dolphin", "hey dolphin", "hello assistant",
        "hi assistant", "hello bot", "hi bot", "morning", "afternoon", "evening"
    }
    if cleaned in EXACT_GREETINGS:
        return True

    # Check introductions like "Hi I am Arun" or "Hello, my name is Captain John"
    if extract_name(q):
        non_greeting_words = [w for w in words if w not in GREETING_WORDS]
        if len(non_greeting_words) <= 2:
            return True

    return False


def is_simple_social_intent(query: str) -> str | None:
    """
    Fast classification for obvious greetings/goodbyes/thanks/well-wishes without expensive GPT call.
    Returns 'GREETING', 'GOODBYE', 'THANK', 'WELL_WISH', or None.
    """
    if not query or not isinstance(query, str):
        return None

    if is_greeting_query(query):
        return "GREETING"

    cleaned = re.sub(r"[^\w\s]", " ", query.lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return None

    # Well-wishes (how are you, etc.)
    wellwish_patterns = {
        "how are you", "how are you doing", "how r you", "how r u",
        "how do you do", "hope you are well", "hope youre well",
        "how are you feeling", "how have you been", "how you doing",
        "hows it going", "what's up", "whats up", "sup", "wassup",
        "how is it going", "how are things"
    }
    if cleaned in wellwish_patterns:
        return "WELL_WISH"

    # Goodbyes
    goodbye_patterns = {
        "bye", "goodbye", "good bye", "see you", "see ya", "see you later",
        "cya", "later", "catch you later", "talk to you later", "ttyl",
        "signing off", "log off", "logout", "gotta go", "gtg", "bye bye",
        "have a good day", "have a nice day"
    }
    if cleaned in goodbye_patterns:
        return "GOODBYE"

    # Thanks
    thank_patterns = {
        "thanks", "thank you", "thank you so much", "thanks a lot",
        "appreciate it", "thx", "ty", "cheers", "much appreciated",
        "thanks so much", "many thanks", "thank u"
    }
    if cleaned in thank_patterns:
        return "THANK"

    return None


class QueryAnalyzer:
    """Improved analyzer with stronger greeting logic + name extraction."""

    # Keywords that should always be treated as QUERY regardless of intent classification
    # This includes workplace safety, crew management, and legitimate operational questions
    PRIORITIZED_KEYWORDS = [
        "nurture yourself",
        "harassment", "harassing", "harassed",
        "bullying", "bullied", "bully",
        "intoxicated", "intoxication", "drunk",
        "crew member", "crew management", "crew safety",
        "workplace safety", "workplace incident",
        "how should", "what should", "how to handle",
        "advice", "need advice", "what do i do",
        "egcs", "scrubber", "scrubbers", "bwms", "vlsfo", "scr", "mepc",
    ]
    def __init__(self, intent_service: GPTIntentService):
        self.intent_service = intent_service

    async def analyze_query(
        self, current_query: str, previous_questions: List[str]
    ) -> Tuple[str, str, List[Dict[str, str]]]:

        # ✅ FIX: await async call
        standalone = await self._generate_standalone_query(
            current_query, previous_questions
        )

        query_lower = standalone.lower().strip()

        # 🚫 ZERO HALLUCINATION GUARD 1: Instant Off-Topic / Non-Marine Filter
        if is_off_topic_query(standalone) or is_off_topic_query(current_query):
            logger.info(f"[ANALYZER] 🚫 Off-topic query detected: '{standalone}' (current='{current_query}') → OFF_TOPIC")
            category = "OFF_TOPIC"
        # Fast-path 1: Check for simple intents (greetings, thanks, goodbyes, well-wishes)
        elif (simple_intent := self._is_simple_intent(current_query) or self._is_simple_intent(standalone)):
            logger.info(f"[ANALYZER] ⚡ Fast-path: '{current_query}' → {simple_intent} (skipped GPT)")
            category = simple_intent
        elif any(kw in query_lower for kw in self.PRIORITIZED_KEYWORDS):
            logger.info(f"[ANALYZER] ⚡ Prioritized keyword detected in query: {standalone}. Forcing category QUERY.")
            category = "QUERY"
        else:
            # Fast-path 2: Check rule-based classifier for QUIZ / SUMMARY
            rule_cat = await self._classify_query(standalone)
            if rule_cat in {"QUIZ_REQUEST", "SUMMARY_REQUEST"}:
                logger.info(f"[ANALYZER] ⚡ Rule-based classification: '{standalone}' → {rule_cat}")
                category = rule_cat
            # Fast-path 3: Clear marine technical query pattern
            elif is_obvious_marine_query(standalone) or is_obvious_marine_query(current_query):
                logger.info(f"[ANALYZER] ⚡ Obvious marine query detected: '{standalone}' → QUERY (skipped GPT)")
                category = "QUERY"
            elif self._looks_like_marine_acronym(standalone) or self._looks_like_marine_acronym(current_query):
                logger.info(f"[ANALYZER] '{standalone}' (or '{current_query}') looks like marine acronym, using category QUERY")
                category = "QUERY"
            elif self._looks_like_technical_term(standalone) or self._looks_like_technical_term(current_query):
                logger.info(f"[ANALYZER] '{standalone}' looks like technical term, skipping GPT, using rule-based classification")
                category = "QUERY"
            else:
                # Ambiguous or non-obvious query: evaluate with GPT Intent Service
                logger.info(f"[ANALYZER] Evaluating intent via GPT for '{standalone}'...")
                gpt_intent = await self.intent_service.classify_intent(standalone)

                if gpt_intent in ("GOODBYE", "GREETING", "OFF_TOPIC") and self._looks_like_technical_term(standalone):
                    logger.info(f"[ANALYZER] Overriding false GPT intent '{gpt_intent}' to QUERY for technical term: '{standalone}'")
                    category = "QUERY"
                elif gpt_intent in {"GREETING", "GOODBYE", "THANK", "WELL_WISH", "THREADING", "NEGATIVE", "OFF_TOPIC"}:
                    category = gpt_intent
                else:
                    category = gpt_intent or rule_cat

        # ✅ FIX: await async call
        messages = await self._create_analysis_prompt(
            standalone, category, previous_questions
        )

        return standalone, category, messages
    
    def _is_simple_intent(self, query: str) -> str | None:
        """
        Fast classification for obvious greetings/goodbyes/thanks without expensive GPT call.
        """
        return is_simple_social_intent(query)

        
    def _is_obvious_query(self, query: str) -> bool:
        """
        Check if query is clearly an informational question or operational inquiry.
        Only returns True if it is explicitly a maritime domain query and not off-topic.
        """
        return is_obvious_marine_query(query)

    def _looks_like_marine_acronym(self, query: str) -> bool:
        """
        Check if query contains or looks like a legitimate marine technical acronym/term.
        Criteria:
        - Contains an acronym from the centralized maritime acronyms database
        - Or matches known maritime indicators (case-insensitive)
        """
        if not query or is_off_topic_query(query):
            return False

        # 1. Direct check using centralized maritime acronym database
        try:
            from services.maritime_acronyms import find_acronyms_in_query
            if find_acronyms_in_query(query):
                return True
        except Exception:
            pass

        # 2. Check full query against domain indicators
        if is_marine_domain_query(query):
            return True

        # 3. Check individual candidate tokens (2-6 chars, letters or numbers)
        q = query.strip()
        tokens = re.findall(r'\b[a-zA-Z0-9_\-\/]{2,6}\b', q)
        for t in tokens:
            if is_marine_domain_query(t):
                return True

        return False

    def _looks_like_technical_term(self, query: str) -> bool:
        """
        Check if query looks like a technical term/acronym/machinery phrase that should skip GPT classification.
        """
        if not query or is_off_topic_query(query):
            return False

        q = query.strip()
        words = q.split()

        # Single word that's 3+ chars and alphanumeric (e.g. BBS, BOG, BOB, pumps, valves, hazards)
        if len(words) == 1 and len(q) >= 3 and q.replace('-', '').replace('_', '').isalnum():
            return True

        # 2-3 words, likely a technical phrase (e.g. acurro pump, extension pump, relief valve)
        if 2 <= len(words) <= 3 and not any(w.lower() in ("how", "what", "why", "who", "when", "where", "can", "could", "tell") for w in words):
            return True

        # Contains uppercase (likely acronym)
        if any(c.isupper() for c in q):
            return True

        return self._looks_like_marine_acronym(query)

    async def _generate_standalone_query(
        self, current_query: str, previous_questions: List[str]
    ) -> str:
        """
        Convert conversational queries into clean search terms.
        
        Examples:
        - "Can you explain me SEEMP" → "SEEMP"
        - "What is EEDI" → "EEDI"  
        - "Tell me about ship stability" → "ship stability"
        """
        q = current_query.strip()
        
        # Handle references to previous context
        if not previous_questions:
            # Clean up conversational phrases
            return self._extract_core_query(q)
        
        if q.lower() in {"this", "that", "it"}:
            return f"{q} {previous_questions[-1]}"
        
        # Clean up the query
        return self._extract_core_query(q)
    
    def _extract_core_query(self, query: str) -> str:
        """
        Extract the core search terms from conversational queries.
        
        Robust regex-based approach that handles typos and conversational patterns.
        
        Examples:
        - "Can you explan SEEMP" → "SEEMP"
        - "What is EEDI" → "EEDI"  
        - "Tell me about stability" → "stability"
        - "Hey, I need some advice... someone bullied me" → "bullying crew member advice"
        - "A crew member who seems intoxicated is also harassing others. How should this be handled?" → "crew member intoxicated harassing how to handle"
        """
        import re
        
        query_lower = query.lower().strip()
        original = query_lower
        
        # Pattern 0: Handle conversational openings ("Hey", "Hi", "I need advice", "something happened")
        conversational_openings = r'^(hey|hi|hello|hey there|i need|i\'m asking|something happened|last shift|on my|during my)\s+'
        query_lower = re.sub(conversational_openings, '', query_lower, flags=re.IGNORECASE).strip()
        
        # Pattern 1: Handle "can/could/would you explain/tell/describe/show"
        conversational_prefix = r'^(can|could|would|will|should|may|please|kindly)?\s*(you|i|we)?\s*(please|kindly)?\s*(explain|explan|explai|tell|tel|describe|describ|show|give|provide|get|find|know|help|assist)\s*(me|us|with|about|on)?\s*'
        query_lower = re.sub(conversational_prefix, '', query_lower, flags=re.IGNORECASE).strip()
        
        # Pattern 2: Handle "what/where/when/why/how is/are/does/do" (must match whole auxiliary verb)
        if query_lower == original:  # Only if previous regex didn't match
            wh_pattern = r'^(what|where|when|why|how|who)\s+(is|are|do|does|did|was|were|can|could|will|would|should)\s+'
            query_lower = re.sub(wh_pattern, '', query_lower, flags=re.IGNORECASE).strip()
        
        # Pattern 2.5: Handle "how should/what should" for procedural questions
        procedural_pattern = r'^(how|what)\s+should\s+'
        query_lower = re.sub(procedural_pattern, '', query_lower, flags=re.IGNORECASE).strip()
        
        # Pattern 3: Remove standalone action verbs that might be left over
        action_verbs_standalone = r'^(explain|explan|explai|tell|tel|describe|describ|show|about|advice|advise)\s+'
        query_lower = re.sub(action_verbs_standalone, '', query_lower, flags=re.IGNORECASE).strip()
        
        # Pattern 4: Remove remaining filler words from start
        filler_pattern = r'^(the|a|an|about|regarding|concerning|information|info|details|on|this|that|it)\s+'
        query_lower = re.sub(filler_pattern, '', query_lower, flags=re.IGNORECASE).strip()
        
        # Pattern 5: Extract key phrases from narrative queries (for workplace safety queries)
        # If query contains workplace safety keywords, preserve them even if conversational
        workplace_keywords = [
            "harassment", "harassing", "harassed", "bullying", "bullied", 
            "intoxicated", "intoxication", "crew member", "crew management",
            "workplace", "incident", "misconduct", "safety", "protocol"
        ]
        
        # If query is very conversational but contains workplace keywords, extract those
        if any(kw in original for kw in workplace_keywords):
            # Keep the full query but clean up excessive conversational filler
            # Remove common conversational endings
            query_lower = re.sub(r'\s+(what do i do|what should i do|how do i handle|please help|can you help)\s*$', '', query_lower, flags=re.IGNORECASE).strip()
        
        # Clean up punctuation and trailing questions
        query_lower = query_lower.rstrip("?.,!").strip()
        
        # Remove trailing conversational phrases
        query_lower = re.sub(r'\s+(do\s+you\s+know|can\s+you\s+help|please|thanks|thank\s+you)\s*$', '', query_lower, flags=re.IGNORECASE).strip()
        
        # If we cleaned too much (less than 3 chars), return original (preserve context)
        if not query_lower or len(query_lower) < 3:
            # For very short results, return original to preserve meaning
            return query.strip()
        
        return query_lower

    async def _classify_query(self, query: str) -> str:
        text = query.lower().strip()

        # ---- QUIZ ----
        # Use word boundary matching to avoid false positives (e.g., "testing" shouldn't match "test")
        quiz_patterns = [
            r'\bquiz\b',
            r'\bquizz\b',
            r'\bqusiz\b',
            r'\bmcq\b',
            r'\b(practice\s+)?test\b',  # Matches "test" or "practice test" as whole words
            r'\bmock\s+test\b',
            r'\bquestion\s+paper\b',
            r'\bassessment\b',
            r'\bgive\s+me\s+a\s+quiz\b',
            r'\bgenerate\s+quiz\b',
            r'\bcreate\s+quiz\b',
            r'\bquiz\s+me\b',
            r'\btest\s+me\b',
            r'\bmake\s+a\s+quiz\b',
            r'\bcan\s+you\s+quiz\s+me\b',
        ]
        
        # Check for quiz patterns using word boundaries
        if any(re.search(pattern, text) for pattern in quiz_patterns):
            # Additional check: if query starts with "explain", "what is", "how to", etc., it's likely a query, not quiz
            query_starters = [
                r'^explain\s+',
                r'^what\s+is\s+',
                r'^how\s+to\s+',
                r'^how\s+does\s+',
                r'^tell\s+me\s+about\s+',
                r'^describe\s+',
            ]
            
            # If query starts with explanatory phrases, it's likely a regular query even if it contains "test"
            if any(re.search(starter, text) for starter in query_starters):
                return "QUERY"  # Don't classify as quiz if it's an explanatory query
            
            return "QUIZ_REQUEST"

        # ---- SUMMARY ----
        if any(
            k in text
            for k in [
                "summary",
                "sumary",
                "summarize",
                "summery",
                "overview",
                "brief me",
                "give summary",
                "recap",
                "explain my learnings",
                "summary of my learnings",
                "summaries",
            ]
        ):
            return "SUMMARY_REQUEST"

        # ---- INCOMPLETE ----
        # Allow single words if they look like technical terms or acronyms
        # Only mark as incomplete if it's truly empty or just filler words
        if len(text.split()) < 2:
            # Single word - check if it's meaningful (not just "hi", "ok", etc.)
            if len(text) >= 3 and text.isalpha():  # 3+ letter words are likely valid terms
                return "QUERY"  # Treat as valid query (e.g., "EEDI", "SEEMP", "stability")
            return "INCOMPLETE"

        return "QUERY"

    async def _create_analysis_prompt(
        self, standalone_query: str, category: str, previous_questions: List[str]
    ) -> List[Dict[str, str]]:

        history = " | ".join(previous_questions)
        content = (
            f"Standalone: {standalone_query}\n"
            f"Category: {category}\n"
            f"History: {history}"
        )

        return [{"role": "system", "content": content}]

    async def _extract_short_topic(self, query: str) -> str:
        cleaned = query.translate(str.maketrans("", "", string.punctuation))
        words = cleaned.split()
        return " ".join(words[:3]) if words else "marine topic"


class EnhancedQueryAnalyzer(QueryAnalyzer):

    def __init__(self, intent_service: GPTIntentService):
        super().__init__(intent_service)

    async def classify_for_router(
        self, current_query: str, previous_questions: List[str]
    ) -> Dict:

        # ✅ FIX: already awaited correctly
        standalone_query, category, _ = await self.analyze_query(
            current_query, previous_questions
        )

        category_mapping = {
            "GREETING": "GREETING",
            "GOODBYE": "GOODBYE",
            "THANK": "THANK",
            "WELL_WISH": "WELL_WISH",
            "THREADNING": "THREADNING",
            "NEGATIVE": "NEGATIVE",
            "QUIZ_REQUEST": "QUIZ",
            "SUMMARY_REQUEST": "SUMMARY",
            "OFF_TOPIC": "OFF_TOPIC",
            "QUERY": "QUERY",
            "INCOMPLETE": "FALLBACK",
            "NOT_CLASSIFIED": "FALLBACK",
        }

        router_mapping = {
            "GREETING": "greeting",
            "GOODBYE": "goodbye",
            "THANK": "thank",
            "WELL_WISH": "well_wish",
            "THREADNING": "threadning",
            "NEGATIVE": "negative",
            "QUIZ": "quiz",
            "SUMMARY": "summary",
            "OFF_TOPIC": "fallback",
            "QUERY": "query",
            "FALLBACK": "fallback",
        }

        detected_name = extract_name(standalone_query)

        normalized_category = category_mapping.get(category, "FALLBACK")

        return {
            "node_type": router_mapping.get(normalized_category, "fallback"),
            # FIX: await async call
            "short_topic": await self._extract_short_topic(standalone_query),
            "reason": f"Query classified as {normalized_category}: {current_query}",
            "user_name": detected_name,
            "category": normalized_category,
            "standalone_query": standalone_query,
        }
