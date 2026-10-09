from __future__ import annotations

import json
from typing import Any, Dict, List
from loguru import logger
from graph.base_node import BaseNode
from graph.history_utils import extract_clean_history
from services.openai_service import OpenAIService
from services.suggestion_service import SuggestionService

import re


def strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9]*", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


# --- SAFE ACCESSOR ---
def safe_get(state: Any, key: str, default=None):
    """Allow dict or GraphState safely."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


class QuizNode(BaseNode):
    def __init__(self, openai_service: OpenAIService, suggestion_service: SuggestionService) -> None:
        super().__init__("quiz")
        self.openai_service = openai_service
        self.suggestion_service = suggestion_service

    def _aggregate_media(self, chunks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        seen_ids: set[str] = set()

        def _dedupe(items: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
            if not items:
                return []
            deduped: List[Dict[str, Any]] = []
            for item in items:
                identifier = None
                if isinstance(item, dict):
                    for key in ("Id", "id", "ID"):
                        if key in item and item[key] is not None:
                            identifier = str(item[key])
                            break
                if identifier and identifier in seen_ids:
                    continue
                if identifier:
                    seen_ids.add(identifier)
                deduped.append(item)
            return deduped

        videos: List[Dict[str, Any]] = []
        images: List[Dict[str, Any]] = []
        pdfs: List[Dict[str, Any]] = []

        for chunk in chunks:
            if isinstance(chunk.get("videos"), list):
                videos.extend(chunk.get("videos") or [])
            if isinstance(chunk.get("images"), list):
                images.extend(chunk.get("images") or [])
            if isinstance(chunk.get("pdfs"), list):
                pdfs.extend(chunk.get("pdfs") or [])

        return {"videos": _dedupe(videos), "images": _dedupe(images), "pdfs": _dedupe(pdfs)}

    def _extract_conversation_content(self, history: List[Dict[str, Any]]) -> str:
        """
        Extract recent conversation content for quiz generation.
        Focuses on assistant responses which contain the educational content.
        """
        conversation_content = []

        # Get last 3-5 exchanges (user + assistant pairs)
        recent_history = history[-10:] if len(history) > 10 else history

        for msg in recent_history:
            if not isinstance(msg, dict):
                continue

            role = msg.get("role")
            content = msg.get("content", "")

            # Only use assistant messages (they contain the educational content)
            if role == "assistant" and content:
                # Extract text content (skip quiz payloads)
                if isinstance(content, str):
                    conversation_content.append(content)
                elif isinstance(content, dict):
                    text = content.get("content") or content.get("message") or ""
                    if isinstance(text, str) and text:
                        conversation_content.append(text)

        return "\n\n---\n\n".join(conversation_content)

    def _format_chunk_for_prompt(self, chunk: Dict[str, Any]) -> str:
        """Combine content and media details for the quiz prompt."""
        content = chunk.get("content") or ""
        topic_name = chunk.get("topic_name") or ""

        formatted = f"Topic: {topic_name}\n{content}" if topic_name else content
        return formatted

    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Safe state extraction
        decision = safe_get(state, "router_decision", {})
        chunks: List[Dict[str, Any]] = safe_get(state, "retrieval_chunks", [])
        videos: List[Dict[str, Any]] = safe_get(state, "video_suggestions", [])
        query = safe_get(state, "current_query", "")
        resolved_topic = safe_get(state, "resolved_quiz_topic", "") or query
        history = extract_clean_history(state)
        previous_questions: List[str] = [
            msg["content"] for msg in history if msg.get("role") == "user"
        ]
        messages = safe_get(state, "messages", [])

        media_bundle = self._aggregate_media(chunks)

        query_lower = query.lower().strip()
        is_generic_quiz_request = query_lower in [
            "quiz", "quizz", "qusiz", "mcq", "test", "practice test",
            "give me a quiz", "generate quiz", "create quiz",
            "question paper", "mock test", "assessment",
            "quiz me", "test me", "make a quiz", "can you quiz me"
        ]

        if is_generic_quiz_request and len(history) > 0:
            # ✅ Use conversation history
            content_body = self._extract_conversation_content(history)
            content_source = "conversation history"
            logger.info("[QUIZ] Using CONVERSATION HISTORY as quiz source")
        else:
            # ✅ Use retrieval chunks (for specific topic requests)
            content_body = "\n\n---\n\n".join(
                self._format_chunk_for_prompt(chunk) for chunk in chunks
            )
            content_source = "course retrieval"
            logger.info(f"[QUIZ] Using COURSE RETRIEVAL as quiz source (topic: {resolved_topic})")

        # Refusal logic for insufficient content
        if not content_body or len(content_body.strip()) < 100:
            logger.warning("[QUIZ] Insufficient content for quiz generation")
            quiz_items = [
                {
                    "question": f"I couldn't find enough specific information in the course to generate a quiz on '{resolved_topic}'. Please ask a question about the topic first so I can learn from the context!",
                    "options": [
                        "Tell me about Port State Control",
                        "Explain fatigue management",
                        "Show me available topics",
                        "Help me understand ship stability"
                    ],
                    "correct_index": 0,
                }
            ]
            
            content_payload = {
                "type": "quiz",
                "quiz_items": quiz_items,
                "content": "Insufficient content for quiz generation.",
            }
            
            response = self._build_response(
                content=content_payload,
                chunks_used=chunks,
                video_suggestions=[],
                question_suggestions=self.suggestion_service.generate(
                    query=query,
                    chunks=chunks,
                    history=history,
                    short_topic=resolved_topic,
                    category="quiz",
                ),
                short_topic=resolved_topic,
                routing_reason="insufficient_content",
                media={"videos": [], "images": [], "pdfs": []},
            )
            
            return {
                "router_decision": decision,
                "node_response": self._response_to_dict(response),
                "meaningful_messages": list(safe_get(state, "meaningful_messages", [])) + [{
                    "node_type": self.node_type,
                    "content": content_payload,
                    "user_query": resolved_topic,
                    "category": "QUIZ"
                }],
                "meaningful_history": list(safe_get(state, "meaningful_history", [])) + [{
                    "node_type": self.node_type,
                    "content": content_payload,
                    "user_query": resolved_topic,
                    "category": "QUIZ"
                }],
                "previous_successful_questions": list(safe_get(state, "previous_successful_questions", []) or []),
                "previous_successful_chunks": list(safe_get(state, "previous_successful_chunks", []) or []),
                "last_quiz_chunks": chunks,
                "last_user_query": resolved_topic,
                "last_user_category": "QUIZ",
                "topic_history": list(safe_get(state, "topic_history", []) or []),
            }

        # ✅ Enhanced prompt with conversation awareness
        if is_generic_quiz_request:
            prompt = (
                "You are a quiz generator for marine training. Create a 5-question multiple-choice quiz in JSON.\n\n"
                "CONTEXT: The user has been learning about marine topics in this conversation and now wants to test their knowledge.\n\n"
                "INSTRUCTIONS:\n"
                "1. Generate questions based ONLY on the conversation content provided below\n"
                "2. Focus on the key concepts, definitions, and facts discussed in the conversation\n"
                "3. Each question must have exactly 4 options\n"
                "4. Use zero-based indexing for correct_index (0, 1, 2, or 3)\n"
                "5. Make questions clear and relevant to what was discussed\n"
                "6. If the provided content does not contain sufficient factual information to create 5 high-quality questions, respond ONLY with a JSON object containing a single question explaining this.\n\n"
                "OUTPUT FORMAT (valid JSON only, no markdown):\n"
                "{\n"
                "  \"quiz_items\": [\n"
                "    {\n"
                "      \"question\": \"What is...\",\n"
                "      \"options\": [\"A\", \"B\", \"C\", \"D\"],\n"
                "      \"correct_index\": 1\n"
                "    }\n"
                "  ]\n"
                "}\n\n"
                "CONVERSATION CONTENT TO BASE QUIZ ON:\n"
                f"{content_body}\n\n"
                "Generate 5 questions testing the key concepts from this conversation. Fall back to a single 'insufficient content' question if necessary."
            )
        else:
            prompt = (
                "You are a quiz generator for marine training. Create a 5-question multiple-choice quiz in JSON.\n\n"
                f"USER'S QUIZ REQUEST: \"{resolved_topic}\"\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. Generate questions ONLY about the topic requested by the user above\n"
                "2. If the provided content does not contain information about the requested topic, "
                "respond with a single question explaining that a quiz on this specific topic cannot be generated\n"
                "3. Base all questions strictly on the marine content provided below\n"
                "4. Each question must have exactly 4 options\n"
                "5. Use zero-based indexing for correct_index (0, 1, 2, or 3)\n"
                "6. If the provided content does not contain sufficient factual information to create 5 high-quality questions about this topic, respond ONLY with a JSON object containing a single question explaining this.\n\n"
                "OUTPUT FORMAT (valid JSON only, no markdown):\n"
                "{\n"
                "  \"quiz_items\": [\n"
                "    {\n"
                "      \"question\": \"What is...\",\n"
                "      \"options\": [\"A\", \"B\", \"C\", \"D\"],\n"
                "      \"correct_index\": 1\n"
                "    }\n"
                "  ]\n"
                "}\n\n"
                "MARINE COURSE CONTENT:\n"
                f"{content_body}\n\n"
                f"Remember: Generate quiz questions ONLY about \"{resolved_topic}\" using the content above. Fall back to a single 'insufficient content' question if necessary."
            )

        logger.info(
            "[QUIZ] Generating quiz",
            user_query=query,
            resolved_topic=resolved_topic,
            is_generic_request=is_generic_quiz_request,
            content_source=content_source,
            prompt_length=len(prompt),
        )

        raw = await self.openai_service.chat(
            [{"role": "user", "content": prompt}],
            category="QUIZ",
        )

        logger.info(f"[QUIZ] RAW LLM RESPONSE: {raw}")

        # Extract LLM content safely:
        if isinstance(raw, str):
            quiz_text = raw
        elif isinstance(raw, dict):
            quiz_text = (
                    raw.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    or raw.get("content", "")
                    or ""
            )
        else:
            quiz_text = ""

        quiz_text = strip_code_fences(quiz_text)

        try:
            parsed = json.loads(quiz_text)
            quiz_items = parsed.get("quiz_items") if isinstance(parsed, dict) else None
            if not isinstance(quiz_items, list) or len(quiz_items) == 0:
                raise ValueError("quiz_items missing or empty")

            # Validate quiz items
            for item in quiz_items:
                if not isinstance(item.get("options"), list) or len(item["options"]) != 4:
                    raise ValueError("Each question must have exactly 4 options")
                if not isinstance(item.get("correct_index"), int) or item["correct_index"] not in [0, 1, 2, 3]:
                    raise ValueError("correct_index must be 0, 1, 2, or 3")

            logger.info(f"[QUIZ] Successfully generated {len(quiz_items)} questions")

        except Exception as e:
            logger.error(f"[QUIZ] Failed to parse quiz JSON: {e}")
            quiz_items = [
                {
                    "question": f"I couldn't generate a quiz based on the available content. Would you like to ask about a specific marine topic first?",
                    "options": [
                        "Yes, tell me about Port State Control",
                        "Yes, explain fatigue management",
                        "Yes, describe RightShip audits",
                        "Show me available topics"
                    ],
                    "correct_index": 0,
                }
            ]

        # Determine quiz title
        if is_generic_quiz_request:
            quiz_title = "Quiz time! Test your knowledge from our recent discussion."
        else:
            quiz_title = f"Quiz on {resolved_topic}! Select the best answer for each question."

        content_payload = {
            "type": "quiz",
            "quiz_items": quiz_items,
            "content": quiz_title,
        }

        dynamic_suggestions: List[str] = self.suggestion_service.generate(
            query=query,
            chunks=chunks,
            history=history,
            short_topic=decision.get("short_topic", ""),
            category=decision.get("category") or "quiz",
        )

        response = self._build_response(
            content=content_payload,
            chunks_used=chunks,
            video_suggestions=[],
            question_suggestions=dynamic_suggestions,
            short_topic=decision.get("short_topic", resolved_topic),
            routing_reason=decision.get("reason", "quiz"),
            media={"videos": [], "images": [], "pdfs": []},
        )

        response_dict = self._response_to_dict(response)

        meaningful_messages: List[Dict[str, Any]] = list(safe_get(state, "meaningful_messages", []))
        meaningful_history: List[Dict[str, Any]] = list(safe_get(state, "meaningful_history", []))

        history_entry = {
            "node_type": self.node_type,
            "content": content_payload,
            "short_topic": decision.get("short_topic"),
            "user_query": resolved_topic,
            "chunks": chunks,
            "metadata": response.get("metadata", {}),
            "category": decision.get("category"),
        }

        updated_meaningful_messages = meaningful_messages + [history_entry]
        updated_meaningful_history = meaningful_history + [history_entry]

        previous_successful_questions: List[str] = list(
            safe_get(state, "previous_successful_questions", []) or []
        )
        previous_successful_chunks: List[List[Dict[str, Any]]] = list(
            safe_get(state, "previous_successful_chunks", []) or []
        )
        topic_history: List[str] = list(safe_get(state, "topic_history", []) or [])

        previous_successful_questions.append(resolved_topic)
        previous_successful_chunks.append(chunks)
        if decision.get("short_topic"):
            topic_history.append(decision.get("short_topic"))

        # MUST return both for Pydantic validation
        return {
            "router_decision": decision,
            "node_response": response_dict,
            "meaningful_messages": updated_meaningful_messages,
            "meaningful_history": updated_meaningful_history,
            "previous_successful_questions": previous_successful_questions,
            "previous_successful_chunks": previous_successful_chunks,
            "last_quiz_chunks": chunks,
            "last_user_query": resolved_topic,
            "last_user_category": "QUIZ",
            "topic_history": topic_history,
        }
