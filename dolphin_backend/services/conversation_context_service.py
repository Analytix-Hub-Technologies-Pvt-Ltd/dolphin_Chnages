"""
Conversation Context Service

Tracks conversation patterns to detect repeated questions and enable
response variation for improved UX.

Features:
- Detects when user asks about the same topic multiple times
- Tracks conversation history and topic coverage
- Provides response variation strategies
- Detects user intent from query phrasing
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from difflib import SequenceMatcher


class ConversationContextService:
    """
    Service for tracking conversation context and detecting repeated questions.
    """
    
    def __init__(self, similarity_threshold: float = 0.65):
        """
        Initialize the conversation context service.
        
        Args:
            similarity_threshold: Threshold for considering questions similar (0-1)
        """
        self.similarity_threshold = similarity_threshold
        logger.info(f"ConversationContextService initialized (similarity_threshold={similarity_threshold})")
    
    def check_recent_topic_coverage(
        self,
        session_history: List[Dict[str, Any]],
        current_query: str,
        lookback: int = 10
    ) -> Dict[str, Any]:
        """
        Check if we've recently covered this topic in the conversation.
        
        Args:
            session_history: List of previous Q&A exchanges in the session
            current_query: Current user query
            lookback: Number of recent exchanges to check
        
        Returns:
            Dictionary with:
            - already_covered: bool
            - times_asked: int
            - previous_responses: List[str]
            - previous_queries: List[str]
            - should_vary: bool
            - similarity_scores: List[float]
        """
        if not session_history:
            return {
                'already_covered': False,
                'times_asked': 0,
                'previous_responses': [],
                'previous_queries': [],
                'should_vary': False,
                'similarity_scores': []
            }
        
        # Get recent history
        recent = session_history[-lookback:] if len(session_history) > lookback else session_history
        
        # Find similar queries
        topic_matches = []
        similarity_scores = []
        
        for i, entry in enumerate(recent):
            prev_query = (
                entry.get('user_query', '')
                or entry.get('query', '')
                or (entry.get('content', '') if entry.get('role') == 'user' else '')
            )
            if not prev_query:
                continue
            
            similarity = self._calculate_similarity(prev_query, current_query)
            
            if similarity >= self.similarity_threshold:
                match_entry = dict(entry)
                if entry.get('role') == 'user':
                    if i + 1 < len(recent) and recent[i + 1].get('role') == 'assistant':
                        match_entry['content'] = recent[i + 1].get('content')
                    elif i - 1 >= 0 and recent[i - 1].get('role') == 'assistant':
                        match_entry['content'] = recent[i - 1].get('content')
                topic_matches.append(match_entry)
                similarity_scores.append(similarity)
                logger.info(
                    f"[CONTEXT] Found similar query (similarity={similarity:.2f}): "
                    f"'{prev_query[:50]}' vs '{current_query[:50]}'"
                )
        
        times_asked = len(topic_matches)
        already_covered = times_asked > 0
        should_vary = times_asked >= 1
        
        # Extract responses and queries safely
        previous_responses = []
        for m in topic_matches:
            content = m.get('content')
            if not content:
                continue
            if isinstance(content, dict):
                # Handle structured content (e.g. quiz payloads)
                content = content.get('content') or content.get('message') or str(content)
            if isinstance(content, str):
                previous_responses.append(content)
        previous_queries = [m.get('user_query', '') or m.get('query', '') for m in topic_matches]
        
        if already_covered:
            logger.warning(
                f"[CONTEXT] Topic '{current_query[:50]}' asked {times_asked} time(s) recently. "
                f"Should vary response!"
            )
        
        return {
            'already_covered': already_covered,
            'times_asked': times_asked,
            'previous_responses': previous_responses,
            'previous_queries': previous_queries,
            'should_vary': should_vary,
            'similarity_scores': similarity_scores
        }
    
    def _calculate_similarity(self, query1: str, query2: str) -> float:
        """
        Calculate similarity between two queries.
        
        Uses a combination of:
        1. Token overlap
        2. Sequence matching
        3. Normalized edit distance
        
        Returns:
            Similarity score between 0 and 1
        """
        # Normalize queries
        q1 = self._normalize_query(query1)
        q2 = self._normalize_query(query2)
        
        if not q1 or not q2:
            return 0.0
        
        # If exact match after normalization, return 1.0
        if q1 == q2:
            return 1.0
        
        # Use SequenceMatcher for similarity
        return SequenceMatcher(None, q1, q2).ratio()
    
    def _normalize_query(self, query: str) -> str:
        """
        Normalize a query for comparison.
        
        - Lowercase
        - Remove punctuation
        - Remove common stopwords
        - Strip whitespace
        """
        import re
        import string
        
        # Lowercase
        query = query.lower()
        
        # Remove punctuation
        query = query.translate(str.maketrans('', '', string.punctuation))
        
        # Remove common stopwords (keep important maritime terms)
        stopwords = {
            'can', 'you', 'please', 'me', 'the', 'a', 'an', 'is', 'are', 'what', 
            'how', 'why', 'when', 'where', 'explain', 'tell', 'about'
        }
        words = query.split()
        words = [w for w in words if w not in stopwords or len(w) > 3]
        
        return ' '.join(words)
    
    def detect_user_intent(
        self,
        query: str,
        conversation_context: Dict[str, Any]
    ) -> str:
        """
        Detect user's specific intent from query phrasing and context.
        
        Args:
            query: Current user query
            conversation_context: Result from check_recent_topic_coverage
        
        Returns:
            Intent string: 'simplification', 'more_detail', 'practical', 
            'examples', 'comparison', 'frustrated_repetition', 'general_query'
        """
        query_lower = query.lower()
        times_asked = conversation_context.get('times_asked', 0)
        
        # Check for frustrated repetition (asked 2+ times)
        if times_asked >= 2:
            logger.info(f"[CONTEXT] Detected frustrated_repetition (asked {times_asked} times)")
            return 'frustrated_repetition'
        
        # Check for simplification request
        simplification_signals = ['explain', 'simple', 'eli5', 'basic', 'beginner', 'understand']
        if any(signal in query_lower for signal in simplification_signals):
            return 'simplification'
        
        # Check for more detail request
        detail_signals = ['more', 'detail', 'expand', 'elaborate', 'deeper', 'comprehensive']
        if any(signal in query_lower for signal in detail_signals):
            return 'more_detail'
        
        # Check for practical/procedural request
        practical_signals = ['how to', 'procedure', 'steps', 'do', 'use', 'perform', 'conduct']
        if any(signal in query_lower for signal in practical_signals):
            return 'practical'
        
        # Check for examples request
        example_signals = ['example', 'scenario', 'case', 'situation', 'instance', 'demonstration']
        if any(signal in query_lower for signal in example_signals):
            return 'examples'
        
        # Check for comparison request
        comparison_signals = ['difference', 'vs', 'compare', 'versus', 'contrast', 'between']
        if any(signal in query_lower for signal in comparison_signals):
            return 'comparison'
        
        return 'general_query'
    
    def get_response_strategy(
        self,
        times_asked: int,
        user_intent: str,
        query_style: str = 'normal'
    ) -> Dict[str, Any]:
        """
        Determine how to vary the response based on conversation context.
        
        Args:
            times_asked: Number of times this topic has been asked
            user_intent: Detected user intent
            query_style: Style of query ('ALL_CAPS', 'normal', etc.)
        
        Returns:
            Dictionary with response strategy:
            - approach: str
            - tone: str
            - sections: List[str]
            - acknowledgment: str
            - followup_style: str
        """
        # Base strategies by repetition count
        strategies = {
            0: {  # First time asking
                'approach': 'comprehensive_overview',
                'tone': 'informative_professional',
                'sections': ['introduction', 'key_concepts', 'details', 'conclusion'],
                'acknowledgment': None,
                'followup_style': 'broad_exploration'
            },
            1: {  # Second time asking
                'approach': 'practical_focus',
                'tone': 'conversational_helpful',
                'sections': ['acknowledge_previous', 'practical_aspects', 'examples', 'deeper_details', 'clarify_needs'],
                'acknowledgment': 'acknowledge_covered',
                'followup_style': 'specific_aspects'
            },
            2: {  # Third time asking (frustrated)
                'approach': 'interactive_clarification',
                'tone': 'collaborative_empathetic',
                'sections': ['acknowledge_repetition', 'clarify_intent', 'focused_detail', 'interactive_options'],
                'acknowledgment': 'acknowledge_frustration',
                'followup_style': 'choose_direction'
            }
        }
        
        # Get base strategy (default to strategy for 2+ if more than 2)
        strategy = strategies.get(min(times_asked, 2), strategies[0])
        
        # Adjust based on user intent
        if user_intent == 'simplification':
            strategy['approach'] = 'simplified_explanation'
            strategy['tone'] = 'clear_accessible'
        elif user_intent == 'more_detail':
            strategy['approach'] = 'comprehensive_deep_dive'
            strategy['tone'] = 'detailed_technical'
        elif user_intent == 'practical':
            strategy['approach'] = 'step_by_step_practical'
            strategy['tone'] = 'instructional_clear'
        elif user_intent == 'examples':
            strategy['approach'] = 'scenario_based'
            strategy['tone'] = 'illustrative_engaging'
        elif user_intent == 'frustrated_repetition':
            strategy['approach'] = 'clarify_and_redirect'
            strategy['tone'] = 'empathetic_solution_focused'
        
        # Adjust tone based on query style
        if query_style == 'ALL_CAPS':
            strategy['tone'] = 'clear_concise_direct'
        
        logger.info(
            f"[CONTEXT] Response strategy: approach={strategy['approach']}, "
            f"tone={strategy['tone']}, times_asked={times_asked}, intent={user_intent}"
        )
        
        return strategy
    
    def generate_acknowledgment_text(
        self,
        times_asked: int,
        user_intent: str,
        topic: str
    ) -> Optional[str]:
        """
        Generate acknowledgment text for repeated questions.
        
        Args:
            times_asked: Number of times asked
            user_intent: Detected intent
            topic: Topic being discussed
        
        Returns:
            Acknowledgment text or None if not needed
        """
        if times_asked == 0:
            return None
        
        acknowledgments = {
            1: [
                f"I covered {topic} earlier. Let me provide additional details and practical insights...",
                f"Building on what I explained about {topic}, here are more specific details...",
                f"Since you're asking about {topic} again, let me expand on the practical aspects..."
            ],
            2: [
                f"I notice you're still exploring {topic}. To help better, could you tell me which specific aspect interests you most?",
                f"It seems {topic} is important to your learning. Let me clarify: are you looking for practical procedures, equipment details, or theoretical background?",
                f"I want to make sure I'm addressing your needs on {topic}. What specific information would be most helpful?"
            ]
        }
        
        # Pick appropriate acknowledgment based on repetition
        ack_list = acknowledgments.get(min(times_asked, 2), acknowledgments[1])
        
        # Use hash of topic to get consistent but varied selection
        index = hash(topic) % len(ack_list)
        return ack_list[index]
    
    def generate_followup_options(
        self,
        topic: str,
        times_asked: int,
        previous_responses: List[str]
    ) -> Optional[str]:
        """
        Generate follow-up options for repeated questions.
        
        Args:
            topic: Topic being discussed
            times_asked: Number of times asked
            previous_responses: Previous responses on this topic
        
        Returns:
            Follow-up options text or None if not needed
        """
        if times_asked < 1:
            return None
        
        # For second time: offer clarification
        if times_asked == 1:
            return f"""
I notice you're asking about {topic} again. I can help you explore:
1. 🔍 **Practical Applications** - How this is used in real operations
2. ⚙️ **Technical Details** - In-depth technical specifications
3. 📋 **Procedures** - Step-by-step operational procedures
4. 🎯 **Examples** - Real-world scenarios and case studies

Which aspect would you like to focus on?
"""
        
        # For third+ time: be more explicit about needing direction
        if times_asked >= 2:
            return f"""
I want to ensure I'm providing the information you need about {topic}. Could you help me by specifying:
- Are you looking for **equipment specifications**?
- Do you need **operational procedures**?
- Would **practical examples** be more helpful?
- Or is there a **specific aspect** I haven't covered yet?

This will help me tailor my response to exactly what you're looking for.
"""
        
        return None
    
    def summarize_previous_coverage(
        self,
        previous_responses: List[str],
        max_length: int = 200
    ) -> str:
        """
        Summarize what was covered in previous responses.
        
        Args:
            previous_responses: List of previous response texts
            max_length: Maximum length of summary
        
        Returns:
            Summary of previous coverage
        """
        if not previous_responses:
            return "No previous coverage."
        
        # Extract key topics from previous responses
        # Simple approach: take first 200 chars of each response
        summaries = []
        for i, response in enumerate(previous_responses, 1):
            if response:
                snippet = response[:max_length].replace('\n', ' ').strip()
                if len(response) > max_length:
                    snippet += "..."
                summaries.append(f"Previous response {i}: {snippet}")
        
        return "\n".join(summaries)
