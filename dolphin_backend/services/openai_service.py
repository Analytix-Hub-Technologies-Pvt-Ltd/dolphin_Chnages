# services/openai_service.py
from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Dict, List
from openai import AsyncOpenAI
from loguru import logger
from config import settings
from models.database import get_pool
import json

class OpenAIService:
    """Wrapper around the OpenAI async client for chat and embeddings."""

    def __init__(self) -> None:
        # Modern OpenAI SDK initialization
        # ⚡ OPTIMIZATION: timeout=30s prevents indefinite hangs
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=30.0,
        )
        self.model = settings.openai_model
        # Align defaults with platform configuration for deterministic, grounded outputs
        self.temperature = settings.openai_temperature
        self.max_tokens = settings.openai_max_tokens
        self.embedding_model = "text-embedding-3-large"
        self.embedding_dim = 3072
        self._embedding_cache: Dict[str, List[float]] = {}
        self._embedding_inflight: Dict[str, asyncio.Future] = {}
        logger.info("🔧 Using embedding model: text-embedding-3-large (3072 dims)")

    async def chat(
        self,
        messages: List[dict],
        temperature: float | None = None,
        *,
        category: str = "UNKNOWN",
        model: str | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        """
        Execute a chat completion using OpenAI model.
        """
        active_temperature = self.temperature if temperature is None else temperature
        active_model = model or self.model
        active_max_tokens = max_tokens if max_tokens is not None else self.max_tokens

        normalized_category = category.strip().upper() if isinstance(category, str) else "UNKNOWN"
        if not normalized_category:
            normalized_category = "UNKNOWN"

        prompt_string = "\n\n".join(
            [m.get("content", "") if isinstance(m, dict) else str(m) for m in messages]
        )
        debug_ctx = getattr(self, "debug_prompt_context", None)
        if debug_ctx and debug_ctx.get("session_messages"):
            context_parts = [
                f"node_type: {debug_ctx.get('node_type')}",
                f"standalone_query: {debug_ctx.get('standalone_query')}",
                f"user_details: {json.dumps(debug_ctx.get('user_details', {}), indent=2)}",
                f"session_summary: {debug_ctx.get('session_summary')}",
                f"session_messages: {debug_ctx.get('session_messages')}",
                f"previous_successful_messages: {debug_ctx.get('previous_successful_messages') or []}",
                f"previous_successful_questions: {debug_ctx.get('previous_successful_questions') or []}",
                f"chunk_context: {debug_ctx.get('chunk_context')}",
                f"video_suggestions: {debug_ctx.get('video_suggestions')}",
                f"question_suggestions: {debug_ctx.get('question_suggestions')}",
                "LLM Prompt:",
                prompt_string,
            ]
            prompt_string = "\n".join(context_parts)

        logger.info(
            f"Calling OpenAI chat completion model={active_model} temp={active_temperature} max_tokens={active_max_tokens}"
        )

        try:
            kwargs = {
                "model": active_model,
                "temperature": active_temperature,
                "max_tokens": active_max_tokens,
                "messages": messages,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format

            response = await self.client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            response_content = getattr(getattr(choice, "message", None), "content", "")

            await self._log_llm_call(prompt_string, response_content, normalized_category)

            return response_content

        except Exception as e:
            logger.error(f"❌ OpenAI chat completion error: {e}")
            try:
                await self._log_llm_call(prompt_string, f"ERROR: {e}", normalized_category)
            except Exception:
                logger.exception("Failed to log LLM error response")
            return "I apologize, but I encountered an error processing your request."

    async def embed(self, text: str) -> List[float]:
        """
        Generate vector embedding for a text document using OpenAI embedding model.
        """
        # ROBUST INPUT VALIDATION AND CLEANING
        logger.debug(f"🔍 Embedding input - Type: {type(text)}, Value: {repr(text)[:200]}")

        # Handle different input types
        original_type = type(text)
        if text is None:
            text = "marine topic"
            logger.warning("⚠️ None input converted to 'marine topic'")
        elif isinstance(text, list):
            # If it's a list, take the first string element or convert to string
            if len(text) > 0 and isinstance(text[0], str):
                text = text[0]
            else:
                text = str(text)
            logger.warning(f"⚠️ List input converted to string: {text[:100]}...")
        elif not isinstance(text, str):
            text = str(text)
            logger.warning(f"⚠️ {original_type} input converted to string: {text[:100]}...")

        # Clean and validate the text
        text = text.strip()
        if not text:
            text = "marine topic"
            logger.warning("⚠️ Empty input converted to 'marine topic'")

        # Truncate very long texts (OpenAI has limits)
        if len(text) > 8000:
            text = text[:8000]
            logger.warning("⚠️ Input truncated to 8000 characters")

        logger.debug(f"🔍 Final embedding text: '{text}'")
        cache_key = f"{self.embedding_model}:{text.strip().lower()}"
        if hasattr(self, "_embedding_cache") and cache_key in self._embedding_cache:
            logger.debug("⚡ Reusing cached embedding vector")
            return self._embedding_cache[cache_key]

        if not hasattr(self, "_embedding_inflight"):
            self._embedding_inflight = {}

        if cache_key in self._embedding_inflight:
            logger.debug(f"⚡ In-flight deduplication: joining pending embedding task for '{text[:40]}'")
            try:
                return await self._embedding_inflight[cache_key]
            except Exception:
                pass

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        future: asyncio.Future = loop.create_future()
        self._embedding_inflight[cache_key] = future

        logger.debug(f"Calling OpenAI embedding model={self.embedding_model}")

        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
            )

            embedding = response.data[0].embedding
            logger.debug(f"✅ Embedding generated successfully, dimensions: {len(embedding)}")
            if len(embedding) != self.embedding_dim:
                logger.warning(
                    "⚠️ Embedding dimension mismatch. Expected {}, got {}. Fixing length.",
                    self.embedding_dim,
                    len(embedding),
                )
                embedding = (embedding + [0.0] * self.embedding_dim)[: self.embedding_dim]

            if hasattr(self, "_embedding_cache"):
                if len(self._embedding_cache) > 5000:
                    self._embedding_cache.clear()
                self._embedding_cache[cache_key] = embedding

            if not future.done():
                future.set_result(embedding)

            return embedding

        except Exception as e:
            logger.error(f"❌ OpenAI embedding error: {e}")
            fallback_vec = [0.0] * self.embedding_dim
            if not future.done():
                future.set_result(fallback_vec)
            return fallback_vec

        finally:
            self._embedding_inflight.pop(cache_key, None)
        
    async def stream_chat(
        self,
        messages: List[dict],
        temperature: float | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> AsyncGenerator[str, None]:

        active_temperature = (
            self.temperature if temperature is None else temperature
        )
        active_model = model or self.model
        active_max_tokens = max_tokens if max_tokens is not None else self.max_tokens

        try:
            kwargs = {
                "model": active_model,
                "messages": messages,
                "temperature": active_temperature,
                "max_tokens": active_max_tokens,
                "stream": True,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format

            stream = await self.client.chat.completions.create(**kwargs)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content

        except Exception as e:
            logger.exception(f"❌ Streaming error: {e}")    

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate vector embeddings for multiple texts in a single API call.
        OpenAI supports up to 2048 texts per batch for text-embedding-3-large.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (one per input text)
        """
        if not texts:
            logger.warning("⚠️ Empty texts list provided to embed_batch")
            return []
        
        # Clean and validate all texts
        cleaned_texts = []
        for i, text in enumerate(texts):
            # Handle different input types
            if text is None:
                text = "marine topic"
                logger.warning(f"⚠️ Text[{i}]: None input converted to 'marine topic'")
            elif isinstance(text, list):
                if len(text) > 0 and isinstance(text[0], str):
                    text = text[0]
                else:
                    text = str(text)
                logger.warning(f"⚠️ Text[{i}]: List input converted to string")
            elif not isinstance(text, str):
                text = str(text)
                logger.warning(f"⚠️ Text[{i}]: {type(text)} input converted to string")
            
            # Clean and validate
            text = text.strip()
            if not text:
                text = "marine topic"
                logger.warning(f"⚠️ Text[{i}]: Empty input converted to 'marine topic'")
            
            # Truncate very long texts (OpenAI has limits)
            if len(text) > 8000:
                text = text[:8000]
                logger.warning(f"⚠️ Text[{i}]: Input truncated to 8000 characters")
            
            cleaned_texts.append(text)
        
        logger.debug(f"🔍 Batch embedding {len(cleaned_texts)} texts")
        
        try:
            # OpenAI API supports batch embedding with list input
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=cleaned_texts,
            )
            
            # Extract embeddings in order
            embeddings = []
            for i, data in enumerate(response.data):
                embedding = data.embedding
                
                # Validate and fix dimensions if needed
                if len(embedding) != self.embedding_dim:
                    logger.warning(
                        f"⚠️ Embedding[{i}] dimension mismatch. Expected {self.embedding_dim}, got {len(embedding)}"
                    )
                    embedding = (embedding + [0.0] * self.embedding_dim)[: self.embedding_dim]
                
                embeddings.append(embedding)
            
            logger.debug(f"✅ Batch embedding completed: {len(embeddings)} vectors generated")
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ OpenAI batch embedding error: {e}")
            # Return zero vectors as fallback
            return [[0.0] * self.embedding_dim for _ in range(len(cleaned_texts))]

    async def _log_llm_call(self, prompt: str, response: str, category: str) -> None:
        """Persist LLM interactions for auditing and analytics."""

        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO open_ai_log (input_llm, output_llm, query_category, created_at, updated_at)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    prompt,
                    response,
                    category,
                )
        except Exception:
            logger.exception("Failed to log LLM call to database")



    async def summarize_session(self, messages, existing_summary=None) -> str:
        """
        Single evolving summary (3–4 lines max, NO chunking)
        """

        import json

        # Normalize messages
        if isinstance(messages, str):
            try:
                messages = json.loads(messages)
            except:
                messages = [{"role": "user", "content": messages}]

        if not isinstance(messages, list):
            messages = [{"role": "user", "content": str(messages)}]

        formatted_messages = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}"
            for m in messages
        )

        # CRITICAL PROMPT (forces merge)
        if existing_summary:
            content = f"""
    You are maintaining ONE unified summary of a conversation.

    STRICT RULES:
    - ONLY ONE Subject line (never repeat it)
    - DO NOT create multiple summaries
    - DO NOT append new sections
    - MERGE all information into ONE summary
    - Maximum 3–4 lines total
    - Combine advantages, disadvantages, definitions into same summary
    - Avoid repetition completely
    - Keep it clean and meaningful

    FORMAT:
    Subject: ...
    <2–3 lines summary>

    Existing summary:
    {existing_summary}

    Conversation:
    {formatted_messages}
    """
        else:
            content = f"""
    Create a SHORT unified summary.

    RULES:
    - ONLY ONE Subject line
    - Maximum 3–4 lines
    - Combine all key points into one summary
    - No repetition

    Conversation:
    {formatted_messages}
    """

        prompt = [
            {
                "role": "system",
                "content": "You maintain a single clean evolving summary (max 4 lines).",
            },
            {
                "role": "user",
                "content": content,
            },
        ]

        summary = (await self.chat(prompt, category="SUMMARY")).strip()

        # REMOVE duplicate "Subject:"
        lines = summary.split("\n")
        cleaned = []
        subject_seen = False

        for line in lines:
            if line.strip().startswith("Subject:"):
                if subject_seen:
                    continue
                subject_seen = True
            cleaned.append(line.strip())

        # HARD LIMIT (max 4 lines)
        return "\n".join(cleaned[:4])