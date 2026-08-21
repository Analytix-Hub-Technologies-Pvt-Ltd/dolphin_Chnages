from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from loguru import logger
from pydantic import BaseModel

from graph.build_graph import build_graph
from pipeline.company_retrieval import company_retrieval_node
from retrieval.faiss_store import DEFAULT_TOP_K, FAISSStore
from retrieval.postgres_loader import PostgresLoader
from services.embedding_config import EMBEDDING_DIM
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService
from services.query_analyzer import EnhancedQueryAnalyzer
from services.session_service import SessionService
from services.suggestion_service import SuggestionService
from models.node_response import NodeResponse
from models.database import get_pool
from services.gpt_intent_service import GPTIntentService
from config import settings

from pipeline.chat_pipeline import ChatPipeline

from pipeline.router import router_node
from pipeline.retrieval import retrieval_node
from pipeline.query import query_node
from pipeline.summary import summary_node
from pipeline.quiz import quiz_node
from pipeline.greeting import greeting_node
from pipeline.fallback import fallback_node
from pipeline.goodbye import goodbye_node
from pipeline.thank import thank_node
from pipeline.well_wish import well_wish_node
from pipeline.threadning import threadning_node
from pipeline.negative import negative_node
from fastapi import APIRouter, HTTPException
from retrieval.faiss_store import FAISSStore
from config import settings
from services.image_service import ImageService
from pipeline.company_query import company_query_node

def normalize_video_url(url: str) -> str:
    """
    Normalize video URL for consistent deduplication.
    
    - Converts to lowercase
    - Removes trailing slashes
    - Normalizes http/https (keeps https)
    - Removes common query parameters that don't affect video identity
    - Strips whitespace
    
    Args:
        url: Raw video URL string
        
    Returns:
        Normalized URL string for deduplication
    """
    if not url or not isinstance(url, str):
        return ""
    
    # Strip whitespace
    normalized = url.strip()
    
    if not normalized:
        return ""
    
    # Convert to lowercase
    normalized = normalized.lower()
    
    # Normalize http/https - prefer https
    if normalized.startswith("http://"):
        normalized = normalized.replace("http://", "https://", 1)
    elif not normalized.startswith("https://") and not normalized.startswith("//"):
        # Add https:// if no protocol
        if normalized.startswith("//"):
            normalized = "https:" + normalized
        elif "://" not in normalized:
            normalized = "https://" + normalized
    
    # Remove trailing slash
    normalized = normalized.rstrip("/")
    
    # Remove common query parameters that don't affect video identity
    # Keep video_id, id, v parameters as they might be important
    if "?" in normalized:
        base_url, query = normalized.split("?", 1)
        # Keep only important query params (video_id, id, v)
        important_params = []
        for param in query.split("&"):
            if param.split("=")[0].lower() in ["v", "id", "video_id", "videoid"]:
                important_params.append(param)
        if important_params:
            normalized = base_url + "?" + "&".join(important_params)
        else:
            normalized = base_url
    
    return normalized


try:  # pragma: no cover - optional dependency shim
    from langgraph.checkpoint.memory import MemorySaver
except Exception:  # pragma: no cover - lightweight fallback for tests
    class MemorySaver:  # type: ignore
        def __init__(self):
            self.storage: Dict[str, Dict[str, Any]] = {}

CHECKPOINTER_FIELDS = [
    "previous_successful_questions",
    "previous_successful_chunks",
    "last_query_chunks",
    "last_quiz_chunks",
    "last_user_query",
    "last_user_category",
    "topic_history",
    # Conversation memory that must flow across nodes
    "messages",
    "session_messages",
    "meaningful_messages",
    "meaningful_history",
]

GLOBAL_CHECKPOINTER_STORE: Dict[str, Dict[str, Any]] = {}
GLOBAL_CHECKPOINTER = MemorySaver()


class VectorStoreAdapter:
    """Async wrapper that embeds queries then searches the underlying FAISS store."""

    def __init__(self, embedder: EmbeddingService, store: FAISSStore) -> None:
        self.embedder = embedder
        self.store = store
    
    def get_all_topic_names(self) -> List[str]:
        """
        GENERIC: Get all topic names from the underlying FAISS store.
        Delegates to store.get_all_topic_names() for dynamic acronym loading.
        """
        return self.store.get_all_topic_names()

    async def search_with_embeddings(
            self,
            query: str,
            k: int = DEFAULT_TOP_K
    ) -> List[Dict[str, Any]]:
        """
        Search using the embedder to generate vectors before querying FAISS.


        NOTE:
        - We *always* embed here and then call `store.search(...)`.
        - We do NOT delegate to `store.search_with_embeddings` to avoid:
          - double embedding,
          - mismatched function signatures.
        """
        logger.info(f"🔍 VectorStoreAdapter searching for: '{query}'")

        if not query or not query.strip():
            logger.warning("Empty query provided to VectorStoreAdapter")
            return []

        try:
            cleaned_query = query.strip()
            logger.error("🔎 Generating embedding for cleaned_query='{}'", cleaned_query)
            query_vector = await self.embedder.embed_query(query)
            if len(query_vector) != EMBEDDING_DIM:
                logger.error("Embedding dimension mismatch. Expected {}, got {}", EMBEDDING_DIM, len(query_vector))
                raise ValueError(
                    f"Embedding dimension mismatch. "
                    f"Expected {EMBEDDING_DIM}, got {len(query_vector)}"
                )

            logger.info(f"✅ Generated embedding, dimensions: {len(query_vector)}")

            if hasattr(self.store, "search"):
                result = self.store.search(query_vector, k=k)
            elif hasattr(self.store, "search_with_embeddings"):
                maybe_result = self.store.search_with_embeddings(cleaned_query, k=k)
                result = await maybe_result if asyncio.iscoroutine(maybe_result) else maybe_result
            else:
                raise AttributeError("Vector store is missing search capability")
            logger.error("📌 FAISS returned {} chunks", len(result))
            logger.info(f"✅ FAISS search returned {len(result)} results")
            return result or []


        except Exception as e:
            logger.exception(f"❌ VectorStoreAdapter search failed: {e}")
            return []


class ChatService:
    def __init__(
            self,
            openai_service: OpenAIService,
            embedder: EmbeddingService,
            store: FAISSStore,
            session_service: SessionService = None,
            redis_client=None,
    ) -> None:

        transcribe_store = FAISSStore(
            index_path="retrieval/transcribe_index.bin",
            meta_path="retrieval/transcribe_index.meta.json",
        )

        transcribe_store.load()

        logger.info(
            f"Transcript FAISS loaded: {transcribe_store.is_loaded}"
        )

        logger.info(
            f"Transcript metadata count: {len(transcribe_store.meta_path)}"
        )

        self.transcribe_vector_store = VectorStoreAdapter(
            embedder,
            transcribe_store,
        )
        company_store = FAISSStore(
            index_path="retrieval/company_index.bin",
            meta_path="retrieval/company_index.meta.json",
        )

        company_store.load()
        logger.info(
            f"Company FAISS loaded: {company_store.is_loaded}"
        )
        logger.info(
            f"Company metadata count: {len(company_store.meta_path)}"
        )

        self.company_vector_store = VectorStoreAdapter(
            embedder,
            company_store,
        )
        
        self.openai_service = openai_service
        self.embedder = embedder
        self.store = store
        self.session_service = session_service
        self.suggestion_service = SuggestionService()
        self.vector_store = VectorStoreAdapter(embedder, store)
        self.image_service = ImageService()
        self.redis_client = redis_client 
        self.checkpointer = GLOBAL_CHECKPOINTER

        # LangGraph graph compiled once
        raw_graph = build_graph(
            openai_service,
            self.suggestion_service,
            self.vector_store,
        )

        try:
            self.graph = raw_graph.compile(checkpointer=self.checkpointer)
        except TypeError:
            self.graph = raw_graph.compile()

        intent_service = GPTIntentService()
        self.analyzer = EnhancedQueryAnalyzer(intent_service)

        # Debug hook for tests and observability

        self._last_state: Dict[str, Any] | None = None

    # ============================================================
    # 🔹 Utilities
    # ============================================================
    def _normalize_category(self, raw_value: Any, default: str = "QUERY") -> str:
        allowed = {"GREETING", "QUERY", "QUIZ", "SUMMARY", "FALLBACK"}
        if isinstance(raw_value, str):
            candidate = raw_value.strip().upper()
            if candidate in allowed:
                return candidate
        return default

    def _clean_messages(self, db_messages: list) -> List[Dict[str, Any]]:
        """Normalize stored messages to the canonical schema."""

        cleaned: List[Dict[str, Any]] = []
        for raw in db_messages or []:
            if not isinstance(raw, dict):
                continue

            role = raw.get("role")
            content = raw.get("content")
            category = self._normalize_category(
                raw.get("category") or raw.get("node_type") or raw.get("type"),
                "QUERY",
            )

            # Canonical role-based messages
            if role in {"user", "assistant"} and content is not None:
                normalized_content = (
                    content if isinstance(content, (dict, list)) else str(content)
                )
                normalized = {
                    "message_id": raw.get("message_id"),
                    "role": role,
                    "content": normalized_content,
                    "timestamp": raw.get("timestamp") or datetime.utcnow().isoformat(),
                    "category": category,
                    "like": raw.get("like"),
                    "command": raw.get("command"),
                }
                if role == "assistant":
                    normalized["like"] = raw.get("like")
                    normalized["video_suggestions"] = list(
                        raw.get("video_suggestions") or []
                    )
                    normalized["videos"] = list(raw.get("videos") or [])
                    normalized["images"] = list(raw.get("images") or [])
                    normalized["pdfs"] = list(raw.get("pdfs") or [])
                    normalized["question_suggestions"] = list(
                        raw.get("question_suggestions") or []
                    )
                cleaned.append(normalized)
                continue

            # Old-schema user
            if "question" in raw:
                question = str(raw.get("question") or "").strip()
                if question:
                    cleaned.append(
                        {
                            "role": "user",
                            "content": question,
                            "timestamp": raw.get("timestamp")
                                         or datetime.utcnow().isoformat(),
                            "category": category,
                        }
                    )
                continue

            # Old-schema assistant
            if "response" in raw:
                response_text = str(raw.get("response") or "").strip()
                if response_text:
                    cleaned.append(
                        {
                            "role": "assistant",
                            "content": response_text,
                            "timestamp": raw.get("timestamp")
                                         or datetime.utcnow().isoformat(),
                            "category": category,
                            "video_suggestions": list(
                                raw.get("video_suggestions") or []
                            ),
                            "question_suggestions": list(
                                raw.get("question_suggestions") or []
                            ),
                        }
                    )

        return cleaned

    def _load_checkpoint_state(self, thread_id: str) -> Dict[str, Any]:
        if not thread_id:
            return {}
        return dict(GLOBAL_CHECKPOINTER_STORE.get(thread_id, {}))

    def _save_checkpoint_state(self, thread_id: str, state: Any) -> None:
        if not thread_id:
            return

        raw_state: Dict[str, Any] = {}
        if isinstance(state, BaseModel):
            raw_state = state.model_dump()
        elif isinstance(state, dict):
            raw_state = state

        if not isinstance(raw_state, dict):
            return

        stored = GLOBAL_CHECKPOINTER_STORE.get(thread_id, {})
        for key in CHECKPOINTER_FIELDS:
            value = None
            if key in raw_state:
                value = raw_state.get(key)
            elif hasattr(state, key):
                value = getattr(state, key)

            if value is None:
                value = []

            if not isinstance(value, list):
                value = [value]

            stored[key] = value
        GLOBAL_CHECKPOINTER_STORE[thread_id] = stored

    async def append_message(
            self,
            session_id: str,
            role: str,
            content: Any,
            category: str,
            metadata: dict | None = None,
            *,
            user_id: str | None = None,
            existing_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Append a single message to chat_sessions.messages with clean schema."""

        if role not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")

        metadata = metadata or {}
        normalized_category = self._normalize_category(category, "QUERY")

        messages: List[Dict[str, Any]] = []
        if existing_messages is not None:
            messages = self._clean_messages(existing_messages)
        elif self.session_service and session_id:
            try:
                session = await self.session_service.get_session(
                    session_id, user_id or "anonymous"
                )
                messages = self._clean_messages(
                    session.get("messages", []) if session else []
                )
            except Exception:
                logger.exception("Failed to load session while appending message")
        
        next_id = max(
            [
                msg.get("message_id") or 0
                for msg in messages
                if isinstance(msg, dict)
            ],
            default=0
        ) + 1 

        new_message = {
            "message_id": next_id,
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "category": normalized_category,
            "command": command if (command := metadata.get("command")) else None,
        }
        new_message.update(metadata)

        if role == "assistant":
            new_message.setdefault("like", None)

            new_message.setdefault(
                "video_suggestions",
                list(metadata.get("video_suggestions") or []),
            )
            new_message.setdefault(
                "question_suggestions",
                list(metadata.get("question_suggestions") or []),
            )

        messages.append(new_message)

        if self.session_service and session_id:
            try:
                await self.session_service.update_session_messages(
                    session_id, messages
                )
            except Exception:
                logger.exception("Failed to persist appended message")

        return messages

    def _coerce_media(self, value: Any) -> List[Dict[str, Any]]:
        """Normalize media payloads into a list of dicts."""

        if isinstance(value, list):
            return value

        if isinstance(value, (str, bytes)):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except Exception as e:
                logger.debug(f"Failed to parse suggestions as JSON: {e}")
                pass

        return []
 
    # def _normalize_video_suggestions(
    #         self, suggestions: List[Any]
    # ) -> List[Dict[str, str]]:
    #     """Ensure each video suggestion has a canonical URL for state validation."""

    #     normalized: List[Dict[str, str]] = []
    #     seen: set[str] = set()

    #     for entry in suggestions or []:
    #         data = entry
    #         if hasattr(entry, "model_dump"):
    #             try:
    #                 data = entry.model_dump()
    #             except Exception:
    #                 data = entry

    #         if not isinstance(data, dict):
    #             continue

    #         # Case-insensitive key extraction
    #         extract = lambda keys, d: next((d[k] for k in keys if k in d), "")

    #         url = str(extract(["url", "videourl", "Url", "videolink", "Link"], data)).strip()
    #         if not url or url in seen:
    #             continue

    #         seen.add(url)

    #         title = str(extract(["title", "Title", "About", "topic_name"], data)).strip()
    #         video_id = str(extract(["video_id", "Id", "id"], data)).strip()
    #         thumbnail = str(extract(["thumbnail", "Thumbnail"], data)).strip()

    #         normalized.append(
    #             {
    #                 "title": title if title else "Course video",
    #                 "url": url,
    #                 "videourl": url,
    #                 "video_id": video_id,
    #                 "thumbnail": thumbnail,
    #             }
    #         )

    #     return normalized

    def _normalize_video_suggestions(
        self,
        suggestions: List[Any],
    ) -> List[Dict[str, str]]:

        normalized: List[Dict[str, str]] = []

        seen_urls = set()
        seen_video_ids = set()

        for entry in suggestions or []:

            data = entry
            if hasattr(entry, "model_dump"):
                try:
                    data = entry.model_dump()
                except Exception:
                    pass

            if not isinstance(data, dict):
                continue

            extract = lambda keys, d: next((d[k] for k in keys if k in d), "")

            url = str(
                extract(["url", "videourl", "Url", "videolink", "Link"], data)
            ).strip()

            video_id = str(
                extract(["video_id", "Id", "id"], data)
            ).strip()

            # Skip duplicates
            if video_id:
                if video_id in seen_video_ids:
                    continue
                seen_video_ids.add(video_id)
            elif url:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
            else:
                continue

            title = str(
                extract(["title", "Title", "About", "topic_name"], data)
            ).strip()

            thumbnail = str(
                extract(["thumbnail", "Thumbnail"], data)
            ).strip()

            normalized.append(
                {
                    "title": title or "Course video",
                    "url": url,
                    "videourl": url,
                    "video_id": video_id,
                    "thumbnail": thumbnail,
                }
            )

        return normalized

    def _normalize_chunk(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure retrieval chunks have consistent fields for downstream nodes."""
        logger.error(
            "RAW CHUNK KEYS = {}",
            list(raw.keys())
        )

        logger.error(
            "RAW TOPIC CODE = {}",
            raw.get("topic_code")
        )

        topic_name = raw.get("topic_name") or raw.get("title") or raw.get("topic") or ""
        topic_content = raw.get("topic_content") or raw.get("content") or raw.get("text") or ""
        combined_content = (
            f"Topic Name: {topic_name}\n\nTopic Content:\n{topic_content}"
            if topic_name or topic_content
            else ""
        )
        # topic_code = str(raw.get("topic_code") or "")
        topic_code = str(raw.get("topic_code") or "")

        logger.error(
            "IMAGE DEBUG topic_code={}",
            topic_code
        )

        images = self.image_service.get_images_by_topic_code(
            topic_code
        )

        logger.error(
            "IMAGE DEBUG image_count={}",
            len(images)
        )
        topic_code = str(raw.get("topic_code") or "")

        
        return {
            "content_id": raw.get("content_id") or raw.get("id"),
            "topic_name": topic_name,
            "topic_code": topic_code,
            "topic_content": topic_content,
            "content": combined_content,
            "videos": self._coerce_media(raw.get("topic_video") or raw.get("videos")),
            # "images": self._coerce_media(raw.get("topic_image") or raw.get("images")),
            "images": images,
            "pdfs": self._coerce_media(raw.get("topic_pdf") or raw.get("pdfs")),
            "keywords": raw.get("keywords") or raw.get("tags") or [],
        }

    def _build_video_suggestions(
            self,
            chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """Create unique video suggestion payloads from retrieved chunks."""

        suggestions: List[Dict[str, str]] = []
        seen_urls: set[str] = set()
        seen_video_ids: set[str] = set()
        seen_titles: set[str] = set()

        logger.debug(
            "Building video suggestions from retrieval chunks",
            chunk_count=len(chunks),
        )

        for chunk in chunks:
            videos = chunk.get("videos") or []
            if not isinstance(videos, list):
                continue

            for video in videos:
                if not isinstance(video, dict):
                    continue

                extract = lambda keys, d: next((d[k] for k in keys if k in d), "")

                raw_url = str(extract(["Url", "url", "videourl", "Link"], video)).strip()
                video_id = str(extract(["Id", "id", "video_id"], video)).strip().lower()
                
                # Extract title - prioritize Title over About, clean HTML if About is used
                title_raw = extract(["Title", "title"], video)
                if not title_raw:
                    title_raw = extract(["About"], video)
                    if title_raw:
                        # Strip HTML tags from About if used as fallback
                        title_raw = re.sub(r'<[^>]+>', '', str(title_raw))
                title = str(title_raw).strip() if title_raw else ""
                normalized_title = title.lower().strip() if title else ""
                
                # Normalize URL for deduplication
                normalized_url = normalize_video_url(raw_url)
                
                # Check for duplicates using URL, video_id, and title
                is_duplicate = False
                if normalized_url and normalized_url in seen_urls:
                    is_duplicate = True
                elif video_id and video_id in seen_video_ids:
                    is_duplicate = True
                elif normalized_title and normalized_title in seen_titles:
                    is_duplicate = True
                elif not normalized_url and not video_id and not normalized_title:
                    # Skip videos with no URL, ID, or title
                    continue
                
                if is_duplicate:
                    continue
                
                # Mark as seen
                if normalized_url:
                    seen_urls.add(normalized_url)
                if video_id:
                    seen_video_ids.add(video_id)
                if normalized_title:
                    seen_titles.add(normalized_title)

                video_id_display = str(extract(["Id", "id", "video_id"], video)).strip()
                thumbnail = str(extract(["Thumbnail", "thumbnail"], video)).strip()
                
                # Use original URL for display
                display_url = raw_url if raw_url else normalized_url

                suggestions.append(
                    {
                        "title": title if title else "Course video",
                        "url": display_url,
                        "videourl": display_url,
                        "video_id": video_id_display,
                        "thumbnail": thumbnail,
                    }
                )
                
                if len(suggestions) >= 3:
                    # Enough suggestions collected; exit inner loop
                    break

            # Exit outer loop if limit reached
            if len(suggestions) >= 3:
                break
        
        logger.debug(
            "Video suggestions built",
            suggestion_count=len(suggestions),
        )
        return self._normalize_video_suggestions(suggestions)

    def _convert_messages_for_llm(
            self,
            raw_messages: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """Convert stored minimal messages into role/content pairs for LangGraph."""

        if self.session_service and hasattr(
                self.session_service, "convert_messages_for_llm"
        ):
            try:
                return self.session_service.convert_messages_for_llm(raw_messages)
            except Exception:
                logger.exception(
                    "Failed to convert messages via session service; "
                    "falling back to local conversion"
                )

        history: List[Dict[str, str]] = []
        for msg in self._clean_messages(raw_messages):
            history.append({"role": msg["role"], "content": msg.get("content", "")})

        return history

    async def _retrieve_chunks(
            self,
            query: str,
            k: int = DEFAULT_TOP_K,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """Embed the query, search FAISS, and return normalized chunks + videos."""

        if not query.strip():
            return [], []

        try:
            raw_chunks = await self.vector_store.search_with_embeddings(query, k=k)

            content_ids: List[int] = []
            for chunk in raw_chunks:
                cid = chunk.get("content_id") or chunk.get("id")
                try:
                    if cid is not None:
                        content_ids.append(int(cid))
                except (TypeError, ValueError):
                    continue

            fetched_rows: Dict[int, Dict[str, Any]] = {}
            if content_ids:
                try:
                    pool = await get_pool()
                    loader = PostgresLoader(pool)
                    fetched_rows = await loader.fetch_course_content_by_ids(content_ids)
                except Exception:
                    logger.exception("Failed to fetch course_content rows for media enrichment")

            retrieval_chunks: List[Dict[str, Any]] = []
            for chunk in raw_chunks:
                cid = chunk.get("content_id") or chunk.get("id")
                merged = dict(chunk)
                try:
                    if cid is not None:
                        record = fetched_rows.get(int(cid))
                        if record:
                            merged = {**merged, **record, "content_id": int(record.get("content_id", cid))}
                except (TypeError, ValueError) as e:
                    logger.debug(f"Failed to convert content_id to int: {cid}, error: {e}")
                    pass
                logger.error(
                    "MERGED CHUNK = {}",
                    merged
                )
                retrieval_chunks.append(self._normalize_chunk(merged))
            video_suggestions = self._build_video_suggestions(retrieval_chunks)

            logger.info(
                "🟩 Retriever returned chunks",
                chunk_count=len(retrieval_chunks),
                video_suggestion_count=len(video_suggestions),
            )
            return retrieval_chunks, video_suggestions
        except Exception:
            logger.exception(
                "⚠️ Retrieval pipeline failed; continuing without contextual chunks"
            )
            return [], []

    # async def _retrieve_transcript_chunks(
    #     self,
    #     query: str,
    #     k: int = 3,
    # ) -> List[Dict[str, Any]]:
    #     """
    #     Search the transcript FAISS index and return matching transcript chunks.
    #     """

    #     if not query or not query.strip():
    #         return []

    #     try:
    #         transcript_chunks = (
    #             await self.transcribe_vector_store.search_with_embeddings(
    #                 query,
    #                 k=k,
    #             )
    #         )

    #         logger.info(
    #             f"🎥 Transcript retrieval returned {len(transcript_chunks)} chunks"
    #         )

    #         return transcript_chunks or []

    #     except Exception as e:
    #         logger.exception(
    #             f"❌ Transcript retrieval failed: {e}"
    #         )
    #         return []

    async def _retrieve_transcript_chunks(
        self,
        query: str,
        k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search the transcript FAISS index and return matching transcript chunks.
        """

        if not query or not query.strip():
            return []

        try:
            transcript_chunks = await self.transcribe_vector_store.search_with_embeddings(
                query,
                k=k,
            )

            logger.info(
                f"🎥 Transcript retrieval returned {len(transcript_chunks)} chunks"
            )

            # Log missing video metadata
            for i, chunk in enumerate(transcript_chunks or [], start=1):
                logger.info(
                    "🎥 Chunk %d | video_id=%s | title=%s | duration=%s | thumbnail=%s",
                    i,
                    chunk.get("video_id"),
                    chunk.get("video_title"),
                    chunk.get("video_duration"),
                    chunk.get("video_thumbnail"),
                )

                if (
                    chunk.get("video_title") is None
                    or chunk.get("video_duration") is None
                    or chunk.get("video_thumbnail") is None
                ):
                    logger.warning(
                        "⚠️ Missing metadata for video_id=%s "
                        "(title=%s, duration=%s, thumbnail=%s)",
                        chunk.get("video_id"),
                        chunk.get("video_title"),
                        chunk.get("video_duration"),
                        chunk.get("video_thumbnail"),
                    )

            return transcript_chunks or []

        except Exception as e:
            logger.exception(
                f"❌ Transcript retrieval failed: {e}"
            )
            return []


    async def get_video_by_topic_and_video_id(
        self,
        topic_code: str,
        video_id: str,
    ) -> dict[str, Any] | None:
        """
        Fetch the matching video object from course_content.topic_video.
        """

        pool = await get_pool()

        async with pool.acquire() as conn:

            row = await conn.fetchrow(
                """
                SELECT topic_video
                FROM public.course_content
                WHERE topic_code = $1
                LIMIT 1
                """,
                topic_code,
            )

        if not row:
            return None

        topic_video = row["topic_video"]

        if isinstance(topic_video, str):
            topic_video = json.loads(topic_video)

        if not isinstance(topic_video, list):
            return None

        for video in topic_video:

            if video.get("Id") == video_id:
                return video

        return None
        
    # ============================================================
    # 🔹 Main chat entrypoint
    # ============================================================
    
    
    async def rewrite_query(
        self,
        current_query: str,
        previous_questions: list[str],
        last_answer: str | None = None,
    ) -> str:
        """
        Convert follow-up query into standalone query
        Supports:
        - normal follow-up
        - reference like "point 2", "this", "that"
        """

        try:
            if not previous_questions:
                return current_query

            last_question = previous_questions[-1]

            prompt = f"""
    You are a query rewriting assistant.

    Previous user question:
    {last_question}

    Last assistant answer:
    {last_answer or "N/A"}

    Current question:
    {current_query}

    Task:
    1. If the current question depends on the previous question → rewrite it as a standalone question.
    2. If the current question refers to:
    - "point 1", "point 2", etc.
    - "this", "that", "above"
    → resolve it using the assistant's last answer.
    3. If the question is independent → return it unchanged.

    Rules:
    - Make it clear and grammatically correct
    - Do not change meaning
    - Do not add extra information
    - Output only the final question

    Examples:

    Q1: What is human error?
    Q2: advantages and disadvantages
    → What are the advantages and disadvantages of human error?

    Answer:
    1. Reduced efficiency
    2. Safety risks
    3. Increased cost

    Q: explain point 2
    → Explain safety risks of human error

    Q: explain this
    → Explain safety risks of human error

    Q1: What is AI?
    Q2: What is ML?
    → What is ML?
    """

            response = await self.openai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
            )

            rewritten = response.strip()

            # fallback safety
            if not rewritten:
                return current_query

            return rewritten

        except Exception as e:
            logger.exception(f"❌ Query rewrite failed: {e}")
            return current_query
        
    async def generate_understanding(
        self,
        query: str
    ) -> str:
        """
        Generate user-friendly understanding summary
        """

        try:
            prompt = f"""
        You are Marine Tutor AI.

        User question:
        {query}

        Task:
        Write a short understanding summary ONLY if the question is related to marine education.

        Rules:
        - If the question is related to marine topics, write 1 short friendly summary
        - If the question is NOT related to marine topics, return exactly: EMPTY
        - Do NOT answer the question
        - Do NOT provide general knowledge
        - Do NOT explain non-marine topics
        - Output ONLY the summary or EMPTY
        """

            response = await self.openai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.3,   # slightly creative
            )

            return response.strip()

        except Exception as e:
            logger.exception(f"❌ Understanding failed: {e}")
            return ""    

    async def run_chat(
        self,
        user_id: str,
        session_id: str,
        db_messages: list,
        current_query: str,
        category: str | None = None,
        user_details: dict | None = None,
    ) -> Tuple[NodeResponse, List[Dict[str, Any]], str, str,Dict[str, Any]]:

        logger.info("Running chat pipeline")

        # -----------------------------
        #  GREETING DETECTION (NEW)
        # -----------------------------
        import re

        def is_greeting(text: str):
            text = text.lower().strip()
            return bool(re.match(r"^(hi|hello|hey|good morning|good evening)\b", text))

        is_user_greeting = is_greeting(current_query)

        # -----------------------------
        #  CLEAN HISTORY
        # -----------------------------
        cleaned_messages = self._clean_messages(db_messages)

        previous_questions = [
            msg.get("content", "")
            for msg in cleaned_messages
            if isinstance(msg, dict) and msg.get("role") == "user"
        ]

        # -----------------------------
        #  QUERY REWRITE (NEW)
        # -----------------------------
        last_answer = None
        for msg in reversed(cleaned_messages):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                last_answer = msg.get("content")
                break

        standalone_query = await self.rewrite_query(
            current_query=current_query,
            previous_questions=previous_questions,
            last_answer=last_answer,
        )

        # understanding_summary = await self.generate_understanding(
        #     standalone_query
        # )
        router_decision = await self.analyzer.classify_for_router(
            current_query,
            previous_questions
        )

        node_type = router_decision.get("node_type", "").lower()

        if node_type == "query":
            understanding_summary = await self.generate_understanding(
                standalone_query
            )
        else:
            understanding_summary = ""

        logger.info(f"🧠 Understanding Summary:\n{understanding_summary}\n")

        logger.info("\n🧾 ===== QUERY DEBUG =====")

        logger.info(f"👉 Current Query:\n{current_query}\n")

        logger.info("Previous Questions:")
        for i, q in enumerate(previous_questions[-3:], 1):  # last 3 only
            logger.info(f"   {i}. {q}")

        logger.info(f"\n💡 Previous Answer:\n{last_answer}\n")

        logger.info(f"🧠 Rewritten Query:\n{standalone_query}")

        logger.info("===== END DEBUG =====\n")

        logger.info(f"🧠 Rewritten Query: {standalone_query}")

        # -----------------------------
        # 2️⃣ ROUTER
        # -----------------------------
        router_decision = await self.analyzer.classify_for_router(
            current_query, previous_questions
        )

        node_type = router_decision.get("node_type", "").lower()
        is_social = node_type in {"greeting", "goodbye", "thank", "well_wish"}

        # -----------------------------
        # ⚡ FAST MODE
        # -----------------------------
        if is_social:
            logger.info(f"⚡ FAST MODE: {node_type}")

            user_category = "GREETING"
            full_history = cleaned_messages
            history_for_llm = []
            meaningful_history = []
            retrieval_chunks = []
            video_suggestions = []
            messages_with_user = cleaned_messages
            checkpoint_state = {}

        # -----------------------------
        # 🧠 NORMAL MODE
        # -----------------------------
        else:
            logger.info(f"🧠 NORMAL MODE: {node_type}")

            if self.session_service and session_id:
                try:
                    session = await self.session_service.get_session(session_id, user_id)
                    existing_title = (session or {}).get("title") if session else None

                    if (not existing_title or existing_title == "Untitled session") and current_query:
                        await self.session_service.update_session_title(session_id, current_query)

                except Exception:
                    logger.exception("❌ Failed to set session title")

            user_category = self._normalize_category(
                category or router_decision.get("category"),
                "QUERY",
            )

            messages_with_user = await self.append_message(
                session_id,
                "user",
                current_query,
                user_category,
                user_id=user_id,
                existing_messages=cleaned_messages,
            )

            full_history = self._clean_messages(messages_with_user)
            history_for_llm = self._convert_messages_for_llm(full_history)

            checkpoint_state = self._load_checkpoint_state(session_id)
            meaningful_history = checkpoint_state.get("meaningful_history", []) or []

            logger.info(f"[MEMORY] Loaded meaningful_history: {len(meaningful_history)}")

        if node_type in {"query", "quiz", "summary"}:

            retrieval_chunks, video_suggestions = await self._retrieve_chunks(
                standalone_query
            )


            # OFF TOPIC CHECK
            query_lower = current_query.lower()

            off_topic_keywords = [
                "movie",
                "movies",
                "film",
                "actor",
                "actress",
                "oscar",
                "cinema",
                "cricket",
                "football",
                "ipl",
                "politics",
                "president",
                "election",
                "tamil movie",
                "hollywood",
                "bollywood",
                "netflix",
                "series",
                "tv show",
                "tv shows",
            ]

            if any(word in query_lower for word in off_topic_keywords):

                logger.info("OFF TOPIC QUESTION DETECTED")

                retrieval_chunks = []
                video_suggestions = []

        else:
            retrieval_chunks = []
            video_suggestions = []
            
        video_suggestions = self._normalize_video_suggestions(
            video_suggestions
        )

        # -----------------------------
        # 🔥 USER PROFILE
        # -----------------------------
        user_profile = user_details or {}
        logger.info(f"✅ USER PROFILE USED: {user_profile}")

        # -----------------------------
        # 3️⃣ BUILD STATE
        # -----------------------------
        state = {
            "current_query": current_query,
            "standalone_query": standalone_query,
            "understanding_summary": understanding_summary,
            "previous_questions": previous_questions,
            "retrieval_chunks": retrieval_chunks,
            "video_suggestions": video_suggestions,
            "meaningful_messages": meaningful_history,
            "meaningful_history": meaningful_history,
            "messages": history_for_llm,
            "session_messages": full_history,
            "user_id": user_id,
            "user_profile": user_profile,
            "company_vector_store": self.company_vector_store, 
            "is_user_greeting": is_user_greeting,
            "node_response": {},
            "router_decision": router_decision,
            "category": user_category,
        }

        state = {**checkpoint_state, **state}

        # -----------------------------
        # NORMALIZE STATE
        # -----------------------------
        for key in ["messages", "session_messages", "meaningful_messages", "meaningful_history"]:
            if state.get(key) is None:
                state[key] = []
            elif not isinstance(state[key], list):
                state[key] = [state[key]]


        try:

            if node_type == "query":

                query_lower = current_query.lower()

                off_topic_keywords = [
                    "movie",
                    "movies",
                    "film",
                    "actor",
                    "actress",
                    "oscar",
                    "cinema",
                    "hollywood",
                    "bollywood",
                    "cricket",
                    "football",
                    "ipl",
                    "politics",
                    "election",
                    "president",
                    "prime minister",
                    "celebrity",
                    "tamil movie",
                    "movie",
                    "movies",
                    "film",
                    "films",
                    "actor",
                    "actress",
                    "oscar",
                    "cinema",
                    "hollywood",
                    "bollywood",
                    "netflix",
                    "series",
                    "tv show",
                    "tv shows"
                ]

                is_off_topic = any(
                    keyword in query_lower
                    for keyword in off_topic_keywords
                )

                if is_off_topic:

                    logger.info("🚫 OFF TOPIC QUESTION DETECTED")

                    state["node_response"] = {
                        "type": "query",
                        "content": (
                            "I am Marine Tutor AI. "
                            "Please ask only maritime, navigation, cargo, "
                            "marine engineering, PSC inspection, COLREGS, "
                            "ship safety, and ship operation questions."
                        ),
                        "sections": [],
                        "chunks_used": [],
                        "videos": [],
                        "images": [],
                        "pdfs": [],
                        "question_suggestions": [
                            "What is anchor watch?",
                            "Explain COLREG Rule 15",
                            "What is boiler design?"
                        ],
                        "metadata": {
                            "routing_reason": "off_topic"
                        }
                    }

                else:

                    state = await retrieval_node(
                        state,
                        self.vector_store,
                        None
                    )

                    state = await company_retrieval_node(
                            state,
                            self.company_vector_store,
                        )

                    state = await query_node(
                        state,
                        self.openai_service,
                        self.suggestion_service,
                        self.vector_store,
                    )

                    state = await company_query_node(
                        state,
                        self.openai_service,
                    )

            else:

                state = await fallback_node(
                    state,
                    self.suggestion_service,
                    self.openai_service,
                )

            raw_result = state

        except Exception as e:
            logger.exception(f"❌ Flow execution failed: {e}")
            raise

        node_response = raw_result.get("node_response")

        validated = NodeResponse.model_validate(node_response)

        assistant_content = validated.content

        if not assistant_content and validated.sections:

            assistant_content = "\n\n".join(
                section.get("content", "")
                for section in validated.sections
                if section.get("content")
            )

        updated_messages = await self.append_message(
            session_id,
            "assistant",
            assistant_content,
            validated.metadata.get("category", "QUERY"),
            validated.metadata,
            user_id=user_id,
            existing_messages=messages_with_user,
        )

        logger.info("========== ASSISTANT SAVE DEBUG ==========")
        logger.info(f"validated.content = {repr(validated.content)}")
        logger.info("==========================================")

        final_cleaned_history = self._clean_messages(updated_messages)

        # return validated, final_cleaned_history, standalone_query
        all_images = []

        seen = set()

        for chunk in retrieval_chunks:
            for image in chunk.get("images", []):

                key = image.get("id") or image.get("base64")

                if key in seen:
                    continue

                seen.add(key)
                all_images.append(image)

        # all_pdfs = []

        # for chunk in retrieval_chunks:
        #     all_pdfs.extend(chunk.get("pdfs", []))

        all_pdfs = []
        seen_pdfs = set()

        for chunk in retrieval_chunks:
            for pdf in chunk.get("pdfs", []):

                key = pdf.get("id") or pdf.get("url")

                if key in seen_pdfs:
                    continue

                seen_pdfs.add(key)
                all_pdfs.append(pdf)

        all_topic_codes = []

        for chunk in retrieval_chunks:
            topic_code = chunk.get("topic_code")

            if topic_code and topic_code not in all_topic_codes:
                all_topic_codes.append(topic_code)

        state["messages"] = updated_messages
        self._last_state = state
        return (
            validated,
            final_cleaned_history,
            standalone_query,
            understanding_summary,
            {
                "videos": video_suggestions,
                "images": all_images,   # add later if you have image retrieval
                "pdfs": all_pdfs,     # add later if needed
                "topic_codes": all_topic_codes,
                "company_answer": state.get("company_answer"),
            }
        )
