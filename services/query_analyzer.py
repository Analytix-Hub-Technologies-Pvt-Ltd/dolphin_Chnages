from __future__ import annotations

import re
import string
import difflib
from typing import Dict, List, Tuple
from loguru import logger
from services.gpt_intent_service import GPTIntentService


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

        # Priority Check: Topics that might look like social phrases or negative feedback
        # but are actually legitimate workplace safety/crew management questions
        query_lower = standalone.lower()
        
        # Fast-path: Check for simple intents first (no GPT call needed)
        # This avoids 300-800ms API latency for obvious greetings/goodbyes
        simple_intent = self._is_simple_intent(standalone)
        if simple_intent:
            logger.info(f"[ANALYZER] ⚡ Fast-path: '{standalone}' → {simple_intent} (skipped GPT)")
            category = simple_intent
        elif any(kw in query_lower for kw in self.PRIORITIZED_KEYWORDS):
            logger.info(f"Prioritized keyword detected in query: {standalone}. Forcing category QUERY.")
            category = "QUERY"
        else:
            # NEW: Check if this looks like a technical query (short, uppercase, alphanumeric)
            # Skip expensive GPT call for obvious technical terms like "EEDI", "SEEMP", etc.
            if self._looks_like_technical_term(standalone):
                logger.info(f"[ANALYZER] '{standalone}' looks like technical term, skipping GPT, using rule-based classification")
                category = await self._classify_query(standalone)
            else:
                # ✅ FIX: await GPT intent service
                gpt_intent = await self.intent_service.classify_intent(standalone)

                dynamic_categories = {"GREETING", "GOODBYE", "THANK", "WELL_WISH", "THREADING", "NEGATIVE"}
                if gpt_intent in dynamic_categories:
                    category = gpt_intent
                else:
                    # ✅ FIX: await async call
                    category = await self._classify_query(standalone)

        # ✅ FIX: await async call
        messages = await self._create_analysis_prompt(
            standalone, category, previous_questions
        )

        return standalone, category, messages
    
    def _is_simple_intent(self, query: str) -> str | None:
        """
        Fast classification for obvious greetings/goodbyes/thanks without expensive GPT call.
        
        Returns the intent category if it's a simple/obvious one, None otherwise.
        This optimization avoids 300-800ms OpenAI API calls for common social phrases.
        
        Examples:
        - "hi" → "GREETING" (no GPT call needed)
        - "how are you" → "WELL_WISH" (no GPT call needed)
        - "thanks" → "THANK" (no GPT call needed)
        - "cargo sampling" → None (needs normal classification)
        """
        query_lower = query.lower().strip()
        
        # Remove punctuation for matching
        query_clean = query_lower.rstrip('.,!?')
        
        # Check spelling variations of greetings/thanks/goodbyes using regex (e.g. hii, heyyy, helloo, yoo)
        # Check greetings
        if re.match(r'^h+i+$', query_clean) or \
           re.match(r'^h+e+y+$', query_clean) or \
           re.match(r'^he+l+o+o*$', query_clean) or \
           re.match(r'^y+o+$', query_clean) or \
           re.match(r'^h+o+l+a+$', query_clean) or \
           re.match(r'^howdy+$', query_clean):
            return "GREETING"
            
        # Check goodbyes
        if re.match(r'^b+y+e+$', query_clean):
            return "GOODBYE"
            
        # Check thanks
        if re.match(r'^t+h+a+n+k+s*$', query_clean) or \
           re.match(r'^t+h+x+$', query_clean) or \
           re.match(r'^t+y+$', query_clean):
            return "THANK"
        
        # Common greetings (single word or short phrases)
        greeting_patterns = {
            "hi", "hello", "hey", "yo", "hola", "howdy", "greetings",
            "good morning", "good afternoon", "good evening", "good day",
            "morning", "afternoon", "evening"
        }
        if query_clean in greeting_patterns:
            return "GREETING"
        
        # Well-wishes (how are you, etc.)
        wellwish_patterns = {
            "how are you", "how are you doing", "how r you", "how r u",
            "how do you do", "hope you are well", "hope you're well",
            "how are you feeling", "how have you been", "how you doing",
            "hows it going", "how's it going", "what's up", "whats up",
            "sup", "wassup"
        }
        if query_clean in wellwish_patterns:
            return "WELL_WISH"
        
        # Goodbyes
        goodbye_patterns = {
            "bye", "goodbye", "good bye", "see you", "see ya", "see you later",
            "cya", "later", "catch you later", "talk to you later", "ttyl",
            "signing off", "log off", "logout", "gotta go", "gtg"
        }
        if query_clean in goodbye_patterns:
            return "GOODBYE"
        
        # Thanks
        thank_patterns = {
            "thanks", "thank you", "thank you so much", "thanks a lot",
            "appreciate it", "thx", "ty", "cheers", "much appreciated",
            "thanks so much"
        }
        if query_clean in thank_patterns:
            return "THANK"
        
        # Not a simple intent - needs normal classification
        return None
    
    def _looks_like_technical_term(self, query: str) -> bool:
        """
        Check if query looks like a technical term/acronym that should skip GPT classification.
        
        Criteria:
        - Short acronym consisting of all-uppercase characters (e.g. "EEDI", "SEEMP", "MARPOL")
        """
        query = query.strip()
        words = query.split()
        
        # Check if the query is a single word or 2-word phrase consisting entirely of uppercase acronyms
        # (e.g. "EEDI", "SEEMP", "MARPOL", "ISM CODE")
        if 1 <= len(words) <= 2:
            is_acronym_phrase = True
            for w in words:
                clean_word = w.replace('-', '').replace('_', '')
                if not (clean_word.isupper() and clean_word.isalnum() and len(clean_word) >= 2):
                    is_acronym_phrase = False
                    break
            if is_acronym_phrase:
                return True
        
        return False

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
