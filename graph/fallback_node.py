from __future__ import annotations

from typing import Any, Dict, List
from graph.base_node import BaseNode
from services.suggestion_service import SuggestionService
from services.openai_service import OpenAIService
from loguru import logger


def safe_get(state: Any, key: str, default=None):
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


FALLBACK_PROMPT = """
You are Marine Tutor AI. A student asked a question that doesn't seem related to maritime course content.

Student Query: "{query}"

Task: Generate a VARIED, encouraging response that:
1. Politely acknowledges their question (VARY your phrasing - don't be repetitive!)
2. Gently suggest they might want to ask about maritime topics
3. Encourage them to explore the marine course material
4. Keep it brief (2-3 sentences)
5. Be warm and helpful, not robotic

CRITICAL: DO NOT use the same phrasing repeatedly. VARY your response each time.

Examples of VARIED responses:
- "That's an interesting question! While it's not directly related to our maritime course content, I'm here to help with ship operations, navigation, safety regulations, and other marine topics. What would you like to explore?"
- "Thanks for reaching out! I specialize in maritime education topics like vessel safety, navigation systems, and marine regulations. Is there a specific marine topic I can help you with?"
- "I appreciate your question! My expertise is focused on maritime course material. I'd be happy to discuss topics like ship stability, cargo operations, or maritime safety. What interests you?"

Generate a UNIQUE, warm response now:
"""


class FallbackNode(BaseNode):
    def __init__(self, suggestion_service: SuggestionService, openai_service: OpenAIService = None) -> None:
        super().__init__("fallback")
        self.suggestion_service = suggestion_service
        self.openai_service = openai_service
        logger.info(f"FallbackNode initialized (LLM-powered={'Yes' if openai_service else 'No'})")

    async def _generate_dynamic_fallback(self, query: str) -> str:
        """Generate varied, non-repetitive fallback message using LLM."""
        if not self.openai_service:
            # Fallback to simple varied messages if no OpenAI service
            import random
            messages = [
                f"Thanks for your question about '{query}'! I specialize in maritime education. What marine topic would you like to explore?",
                f"That's an interesting query! My focus is on maritime course content. I'd be happy to help with ship operations, navigation, or safety topics. What interests you?",
                f"I appreciate your question! I'm here to assist with maritime subjects like vessel safety, navigation systems, and marine regulations. What would you like to learn about?",
            ]
            return random.choice(messages)
        
        try:
            prompt = FALLBACK_PROMPT.format(query=query)
            response = await self.openai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.9,  # High temperature for variety
                category="FALLBACK",
            )
            return response.strip()
        except Exception as e:
            logger.error(f"[FALLBACK] LLM generation failed: {e}")
            return f"I'd love to help! While '{query}' isn't in my maritime course material, I can assist with navigation, ship operations, safety regulations, and more. What would you like to explore?"

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        decision = safe_get(state, "router_decision", {})
        query = safe_get(state, "current_query", "")
        chunks: List[Dict[str, Any]] = safe_get(state, "retrieval_chunks", [])
        previous_questions: List[str] = safe_get(state, "previous_questions", [])
        messages = safe_get(state, "messages", [])
        combined_query = " ".join(q for q in [query] + previous_questions if q)
        
        # Generate dynamic, varied fallback message using LLM
        content = await self._generate_dynamic_fallback(query or combined_query)
        
        category = decision.get("category") or "FALLBACK"
        dynamic_suggestions = self.suggestion_service.generate(
            query=combined_query,
            chunks=chunks,
            history=messages,
            short_topic=decision.get("short_topic", "marine topic"),
            category=category,
        )
        response = self._build_response(
            content=content,
            chunks_used=chunks,
            video_suggestions=[],
            question_suggestions=dynamic_suggestions,
            short_topic=decision.get("short_topic", "marine"),
            routing_reason=decision.get("reason", "fallback"),
        )

        response_dict = self._response_to_dict(response)
        return {
            "router_decision": decision,
            "node_response": response_dict
        }
