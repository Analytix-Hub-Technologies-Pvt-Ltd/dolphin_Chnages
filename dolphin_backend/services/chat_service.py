from __future__ import annotations

import asyncio
import json
import re
import time
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
from services.query_analyzer import EnhancedQueryAnalyzer, is_gap_analysis_request
from services.session_service import SessionService
from services.suggestion_service import SuggestionService
from models.node_response import NodeResponse
from models.database import get_pool
from services.gpt_intent_service import GPTIntentService
from services.scope_messages import get_random_out_of_scope_message
from config import settings

from services.image_manager import ImageManager
from pipeline.chat_pipeline import ChatPipeline

from pipeline.router import router_node
from pipeline.retrieval import (
    retrieval_node,
    extract_videos,
    extract_images,
    normalize_video_item,
    normalize_image_item,
    compute_video_relevance_score,
    compute_image_relevance_score,
    search_matching_videos_in_db,
    search_matching_images_in_db,
)
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
from pipeline.company_query import company_query_node, is_company_query
from services.status_service import get_status_event

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
    
    @property
    def id_to_metadata(self) -> List[Dict[str, Any]]:
        return getattr(self.store, "id_to_metadata", [])

    @property
    def bm25_index(self):
        return getattr(self.store, "bm25_index", None)

    def search_bm25(self, query: str, k: int = 50, filter_fn=None) -> List[Dict[str, Any]]:
        if hasattr(self.store, "search_bm25"):
            return self.store.search_bm25(query, k=k, filter_fn=filter_fn)
        if hasattr(self.store, "bm25_index") and self.store.bm25_index is not None:
            return self.store.bm25_index.search(query=query, top_k=k, filter_fn=filter_fn)
        return []

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
            company_store: FAISSStore = None,
            transcribe_store: FAISSStore = None,
    ) -> None:

        if transcribe_store is None:
            try:
                from api.dependencies import get_transcribe_store
                transcribe_store = get_transcribe_store()
            except Exception:
                transcribe_store = FAISSStore(
                    index_path="retrieval/transcribe_index.bin",
                    meta_path="retrieval/transcribe_index.meta.json",
                )
                transcribe_store.load()

        self.transcribe_vector_store = VectorStoreAdapter(
            embedder,
            transcribe_store,
        )

        if company_store is None:
            try:
                from api.dependencies import get_company_store
                company_store = get_company_store()
            except Exception:
                company_store = FAISSStore(
                    index_path="retrieval/company_index.bin",
                    meta_path="retrieval/company_index.meta.json",
                )
                company_store.load()

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
        allowed = {"GREETING", "QUERY", "QUIZ", "SUMMARY", "FALLBACK", "GAP_ANALYSIS_REQUEST"}
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
                asyncio.create_task(
                    self.session_service.update_session_messages(session_id, messages)
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
        topic_name = raw.get("topic_name") or raw.get("title") or raw.get("topic") or ""
        topic_content = raw.get("topic_content") or raw.get("content") or raw.get("text") or ""
        combined_content = (
            f"Topic Name: {topic_name}\n\nTopic Content:\n{topic_content}"
            if topic_name or topic_content
            else ""
        )
        topic_code = str(raw.get("topic_code") or "")

        # Extract DB images and local image service images
        db_raw_images = self._coerce_media(raw.get("topic_image") or raw.get("images"))
        local_images = []
        if self.image_service and topic_code:
            try:
                local_images = self.image_service.get_images_by_topic_code(topic_code) or []
            except Exception as e:
                logger.debug(f"ImageService lookup failed: {e}")

        combined_images = []
        seen_image_keys = set()

        for img in (db_raw_images + local_images):
            norm_img = normalize_image_item(img, default_title=topic_name)
            if not norm_img:
                continue
            key = norm_img.get("url") or norm_img.get("id")
            if key and key not in seen_image_keys:
                seen_image_keys.add(key)
                combined_images.append(norm_img)

        return {
            "content_id": raw.get("content_id") or raw.get("id"),
            "topic_name": topic_name,
            "topic_code": topic_code,
            "topic_content": topic_content,
            "content": combined_content,
            "videos": self._coerce_media(raw.get("topic_video") or raw.get("videos")),
            "images": combined_images,
            "pdfs": self._coerce_media(raw.get("topic_pdf") or raw.get("pdfs")),
            "keywords": raw.get("keywords") or raw.get("tags") or [],
        }

    def _build_video_suggestions(
            self,
            chunks: List[Dict[str, Any]],
            query: str = "",
    ) -> List[Dict[str, str]]:
        """Create unique video suggestion payloads from retrieved chunks, filtered by relevance to query."""

        suggestions: List[Dict[str, str]] = []
        seen_urls: set[str] = set()
        seen_video_ids: set[str] = set()
        seen_titles: set[str] = set()

        logger.debug(
            "Building video suggestions from retrieval chunks",
            chunk_count=len(chunks),
            query=query,
        )

        for chunk in chunks:
            t_name = chunk.get("topic_name") or ""
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
                
                # If query is provided, check precision relevance
                if query and query.strip():
                    norm_candidate = {
                        "id": video_id,
                        "title": title or t_name,
                        "about": str(video.get("about") or video.get("About") or ""),
                        "url": raw_url,
                    }
                    score = compute_video_relevance_score(norm_candidate, query, t_name)
                    if score < 0.70:
                        continue

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
                        "title": title if title else (t_name or "Course video"),
                        "url": display_url,
                        "videourl": display_url,
                        "video_id": video_id_display,
                        "thumbnail": thumbnail,
                    }
                )

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

            # Direct database keyword search fallback if FAISS index returns 0 results
            if not raw_chunks and query:
                try:
                    pool = await get_pool()
                    async with pool.acquire() as conn:
                        keywords = [w for w in re.split(r'[^a-zA-Z0-9]+', query.strip()) if len(w) > 2 and w.lower() not in {"what", "is", "the", "and", "explain", "how", "process", "for", "with", "about", "tell"}]
                        if keywords:
                            clauses = []
                            params = []
                            for idx, kw in enumerate(keywords[:4], 1):
                                clauses.append(f"(topic_name ILIKE ${idx} OR topic_content ILIKE ${idx})")
                                params.append(f"%{kw}%")
                            if clauses:
                                sql = f"SELECT content_id, topic_name, topic_code, topic_content, topic_video, topic_image, topic_pdf FROM course_content WHERE {' OR '.join(clauses)} LIMIT {k}"
                                db_matches = await conn.fetch(sql, *params)
                                if db_matches:
                                    raw_chunks = [dict(r) for r in db_matches]
                except Exception as ex:
                    logger.debug(f"Direct DB fallback search failed in _retrieve_chunks: {ex}")

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
            video_suggestions = self._build_video_suggestions(retrieval_chunks, query=query)

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

    async def _retrieve_transcript_chunks(
        self,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search the transcript FAISS index and return matching transcript chunks.
        Fallback to targeted database search if transcript index is empty.
        Only returns videos relevant to the query.
        """
        if not query or not query.strip():
            return []

        results = []
        seen = set()

        try:
            if hasattr(self, "transcribe_vector_store") and getattr(self.transcribe_vector_store.store, "is_loaded", False):
                transcript_chunks = await self.transcribe_vector_store.search_with_embeddings(
                    query,
                    k=k,
                )
                for chunk in (transcript_chunks or []):
                    vid_id = chunk.get("video_id") or chunk.get("id")
                    url = chunk.get("video_url") or chunk.get("url") or (f"/storage/videos/{vid_id}.mp4" if vid_id else "")
                    title = chunk.get("video_title") or chunk.get("title") or "Video"
                    # Check relevance
                    if compute_video_relevance_score({"title": title, "about": chunk.get("about", "")}, query) < 0.70:
                        continue
                    if url and url not in seen:
                        seen.add(url)
                        results.append({
                            "id": vid_id,
                            "video_id": vid_id,
                            "title": title,
                            "video_title": title,
                            "url": url,
                            "video_url": url,
                            "thumbnail": chunk.get("video_thumbnail") or chunk.get("thumbnail") or "",
                            "video_thumbnail": chunk.get("video_thumbnail") or chunk.get("thumbnail") or "",
                            "duration": chunk.get("video_duration") or chunk.get("duration") or "",
                            "video_duration": chunk.get("video_duration") or chunk.get("duration") or "",
                        })
        except Exception as e:
            logger.debug(f"Transcript store retrieval error: {e}")

        # Fallback to targeted database search for matching videos
        if not results:
            try:
                db_matched = await search_matching_videos_in_db(query, limit=k)
                for v in db_matched:
                    url = v.get("url") or v.get("Url") or ""
                    vid_id = v.get("id") or v.get("Id") or ""
                    title = v.get("title") or v.get("Title") or "Course Video"
                    key = url or vid_id
                    if key and key not in seen:
                        seen.add(key)
                        results.append({
                            "id": vid_id,
                            "video_id": vid_id,
                            "title": title,
                            "video_title": title,
                            "url": url,
                            "video_url": url,
                            "thumbnail": v.get("thumbnail") or v.get("Thumbnail") or "",
                            "video_thumbnail": v.get("thumbnail") or v.get("Thumbnail") or "",
                            "duration": v.get("duration") or v.get("Duration") or "",
                            "video_duration": v.get("duration") or v.get("Duration") or "",
                        })
            except Exception as e:
                logger.debug(f"Targeted DB video search fallback failed: {e}")

        return results[:k]

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
        conversation_topic: str | None = None,
    ) -> str:
        """
        Convert follow-up query into standalone query
        Supports:
        - deterministic fast-path resolution via followup_resolver
        - normal follow-up
        - reference like "point 2", "this", "that"
        """
        try:
            from services.followup_resolver import (
                is_followup_query,
                resolve_followup_retrieval_query,
                extract_topic_from_query,
                find_substantive_topic_from_history,
            )

            if not previous_questions and not conversation_topic:
                return current_query

            effective_topic = conversation_topic or find_substantive_topic_from_history(previous_questions)

            # 1. Check if the question is a standalone question (not a follow-up)
            if not is_followup_query(current_query, previous_questions or [], effective_topic):
                logger.info(f"⚡ Fast-path: '{current_query}' is already a standalone question (skipped LLM rewrite)")
                return current_query

            # 2. Deterministic follow-up resolution when topic is available
            if effective_topic:
                resolved, _ = resolve_followup_retrieval_query(
                    current_query=current_query,
                    topic=effective_topic,
                    last_answer=last_answer,
                )
                if resolved and resolved != current_query:
                    logger.info(f"⚡ Deterministic follow-up resolution: '{current_query}' -> '{resolved}'")
                    return resolved

            # If last_answer was a generic out-of-scope rejection, find last substantive question
            last_question = previous_questions[-1] if previous_questions else ""
            for q in reversed(previous_questions):
                if q and len(q.strip()) >= 3 and not is_followup_query(q, [], ""):
                    last_question = q
                    break

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
    """

            response = await self.openai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=40,
                model="gpt-4o-mini",
                category="QUERY_REWRITE",
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
        Generate user-friendly understanding summary (bypassed for high-speed response latency).
        """
        return ""

    async def check_query_scope(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """
        Check if the query is in-scope of the available Marine/Maritime course material.
        Returns: "IN-SCOPE", "OUT-OF-SCOPE", or "MIXED".
        """
        # ⚡ Fast-path: Common maritime queries, acronyms, or company procedures are immediately IN-SCOPE
        q_lower = query.lower().strip()
        maritime_fast_terms = {
            "sms", "sop", "sops", "company", "ship", "vessel", "cargo", "tank", "boiler", "engine",
            "pump", "bunker", "bunkering", "ballast", "anchor", "watch", "watchkeeping", "fire",
            "safety", "solas", "marpol", "stcw", "ism", "isps", "colreg", "cow", "crude oil",
            "enclosed space", "permit", "ptw", "deck", "bridge", "navigation", "oow", "chief",
            "master", "captain", "purge", "inert", "igs", "lifeboat", "liferaft", "sopep",
            "mooring", "unmooring", "berth", "berthing", "snap", "snap back", "snap-back", "snapback",
            "winch", "windlass", "bollard", "fairlead", "chock", "bitts", "warping", "rope", "hawsers",
            "towing", "towage", "gangway", "pilot ladder", "rigging", "seamanship"
        }
        if any(term in q_lower for term in maritime_fast_terms) or is_company_query(query, ""):
            return "IN-SCOPE"

        context_parts = []
        for i, chunk in enumerate(chunks[:3], 1):
            name = chunk.get("topic_name", "")
            content = chunk.get("topic_content") or chunk.get("content") or ""
            context_parts.append(f"Source Document {i}: {name}\nContent:\n{content}")
        
        course_context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant course material found in knowledge base."

        prompt = f"""
You are a strict scope control classifier for Marine Tutor AI.
Analyze the User Question and determine whether it is relevant to Marine/Maritime topics or the provided Course Context.

Answering Rules:
1. A question is ALWAYS IN-SCOPE if it relates to ANY maritime, nautical, or shipboard subject, including:
- Marine engineering or Engine-room operations
- Marine operations, Ship operations, Deck operations, Seamanship
- Navigation, Port operations, Ship management, Watchkeeping
- Cargo operations, Cargo loading/unloading, Tank cleaning, Bunkering
- Ballast operations, Stability, Hydrodynamics
- Safety procedures, Maritime safety, Fire safety, Emergency response
- Maritime regulations/conventions (SOLAS, MARPOL, STCW, ISM, ISPS, COLREG)
- Shipboard procedures, Emergency procedures, Lifesaving appliances
- Pollution prevention, Marine environmental protection, Marpol annexes
- Company procedures, SMS, SOPs, Checklists
- Any other topic covered by the available Course Context.

2. A question is OUT-OF-SCOPE ONLY if it is:
- Clearly non-marine / unrelated to maritime (e.g. Python/Java programming, non-marine math, sports, movies, video games, pop culture, cooking, general world history).
- About a famous historical ship accident (e.g., Titanic sinking, Estonia sinking, Costa Concordia) UNLESS there is explicit, specific information about that event/ship in the provided Course Context.
Note: If the query is about genuine commercial maritime, shipping, navigation, engine, or cargo operations, it is ALWAYS IN-SCOPE.

3. Simple conversational phrases or acknowledgements (e.g. 'ok', 'yes', 'sure', 'understand', 'cool', 'continue', 'next') are IN-SCOPE.

4. A question is MIXED if:
- It contains both an in-scope Marine topic and a completely unrelated non-marine topic (e.g. "Explain boiler design and write a Python script for a calculator").

Course Context:
{course_context}

User Question:
{query}

Classify the User Question into exactly one of: IN-SCOPE, OUT-OF-SCOPE, or MIXED.
Output ONLY the classification word: "IN-SCOPE", "OUT-OF-SCOPE", or "MIXED". Do not output anything else.
"""
        try:
            response = await self.openai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=10,
                model="gpt-4o-mini",
                category="SCOPE_CHECK"
            )
            classification = response.strip().upper()
            logger.info(f"Scope Check for query '{query}': {classification}")
            if classification in {"IN-SCOPE", "OUT-OF-SCOPE", "MIXED"}:
                return classification
            if "OUT-OF-SCOPE" in classification:
                return "OUT-OF-SCOPE"
            if "MIXED" in classification:
                return "MIXED"
            return "IN-SCOPE"
        except Exception as e:
            logger.error(f"Scope check failed: {e}")
            return "IN-SCOPE"

    async def rewrite_mixed_query(self, query: str) -> str:
        """
        Rewrite a mixed query to keep only the in-scope Marine topic.
        """
        prompt = f"""
You are an assistant that cleans up mixed user queries for Marine Tutor AI.
The user query contains both a Marine-related topic (in-scope) and an unrelated topic (out-of-scope).
Your task is to rewrite the query to keep ONLY the Marine-related topic. Remove all unrelated topics, questions, or requests (such as programming, math, sports, general knowledge, etc.).

User Question:
{query}

Rewritten Question:
"""
        try:
            response = await self.openai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                category="QUERY_REWRITE"
            )
            rewritten = response.strip()
            logger.info(f"Rewrote mixed query from '{query}' to '{rewritten}'")
            return rewritten if rewritten else query
        except Exception as e:
            logger.error(f"Rewrite mixed query failed: {e}")
            return query

    async def _run_company_retrieval(
        self,
        standalone_query: str,
        current_query: str,
        user_profile: dict,
    ) -> List[Dict[str, Any]]:
        if not self.company_vector_store or not user_profile:
            return []
        has_company = bool(
            user_profile.get("company_id")
            or user_profile.get("company_name")
            or user_profile.get("CompanyName")
            or user_profile.get("company")
        )
        if not has_company:
            return []
        try:
            t_comp_start = time.perf_counter()
            temp_state = {
                "user_profile": user_profile,
                "standalone_query": standalone_query,
                "current_query": current_query,
            }
            res_state = await company_retrieval_node(temp_state, self.company_vector_store)
            c_chunks = res_state.get("company_chunks", []) or []
            logger.info(
                f"⚡ [Company Retrieval Parallel] Retrieved {len(c_chunks)} chunks in {time.perf_counter() - t_comp_start:.3f}s"
            )
            return c_chunks
        except Exception as e:
            logger.warning(f"Parallel company retrieval error: {e}")
            return []

    async def _retrieve_approved_feedback_memory(
        self,
        query: str,
        user_profile: dict,
    ) -> Optional[Dict[str, Any]]:
        """
        Query approved feedback memory for semantically matching preferred responses dynamically.
        Strict company isolation: Company A feedback NEVER influences Company B.
        """
        if not query:
            return None
        user_profile = user_profile or {}
        company_id = (
            user_profile.get("company_id")
            or user_profile.get("company_name")
            or user_profile.get("CompanyName")
            or user_profile.get("company")
            or user_profile.get("cid")
        )
        ship_type = user_profile.get("ship_type") or user_profile.get("shiptype")
        try:
            from services.feedback_memory_service import FeedbackMemoryService
            pool = await get_pool()
            memory_service = FeedbackMemoryService(pool, self.embedder)
            return await memory_service.find_relevant_feedback_preference(
                query=query,
                company_id=str(company_id).strip() if company_id else None,
                ship_type=str(ship_type).strip() if ship_type else None,
                threshold=0.65,
            )
        except Exception as e:
            logger.debug(f"Approved feedback memory retrieval bypassed: {e}")
            return None

    async def run_chat(
        self,
        user_id: str,
        session_id: str,
        db_messages: list,
        current_query: str,
        category: str | None = None,
        user_details: dict | None = None,
        standalone_query: str | None = None,
        understanding_summary: str | None = None,
        on_token: Optional[Any] = None,
    ) -> Tuple[NodeResponse, List[Dict[str, Any]], str, str, Dict[str, Any]]:

        t_chat_total_start = time.perf_counter()
        logger.info("Running chat pipeline (optimized parallel execution)")

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
        #  QUERY REWRITE & PARALLEL UPSTREAM
        # -----------------------------
        last_answer = None
        for msg in reversed(cleaned_messages):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                last_answer = msg.get("content")
                break

        user_profile = user_details or {}
        logger.info(f"✅ USER PROFILE USED: {user_profile}")

        t_upstream_start = time.perf_counter()

        is_user_social = is_user_greeting or bool(re.match(r"^(bye|goodbye|cya|thanks|thank you|thx|well done|good night|have a nice day)\b", current_query.lower().strip()))

        if not standalone_query:
            t_rew_start = time.perf_counter()
            if is_user_social:
                standalone_query = current_query
                router_decision = {"node_type": "greeting" if is_user_greeting else ("goodbye" if "bye" in current_query.lower() else "thank"), "category": "GREETING" if is_user_greeting else "SOCIAL"}
            else:
                rewrite_task = asyncio.create_task(
                    self.rewrite_query(
                        current_query=current_query,
                        previous_questions=previous_questions,
                        last_answer=last_answer,
                    )
                )
                router_task = asyncio.create_task(
                    self.analyzer.classify_for_router(
                        current_query,
                        previous_questions
                    )
                )
                standalone_query, router_decision = await asyncio.gather(rewrite_task, router_task)
            logger.info(f"⚡ Rewritten standalone query in {time.perf_counter() - t_rew_start:.3f}s: '{standalone_query}'")

            node_type_pre = router_decision.get("node_type", "").lower()
            if node_type_pre in {"greeting", "goodbye", "thank", "well_wish"}:
                retrieval_chunks, video_suggestions = [], []
                company_chunks = []
                approved_feedback_memory = None
                checkpoint_state = self._load_checkpoint_state(session_id)
                messages_with_user = await self.append_message(
                    session_id,
                    "user",
                    current_query,
                    "GREETING" if node_type_pre == "greeting" else "QUERY",
                    user_id=user_id,
                    existing_messages=cleaned_messages,
                )
            else:
                if on_token:
                    await on_token(get_status_event("searching"))

                # Launch Course & Company Retrieval, Feedback Memory, Checkpoint loading, and message appending concurrently
                course_task = asyncio.create_task(self._retrieve_chunks(standalone_query))
                company_task = asyncio.create_task(self._run_company_retrieval(standalone_query, current_query, user_profile))
                feedback_task = asyncio.create_task(self._retrieve_approved_feedback_memory(standalone_query, user_profile))
                checkpoint_task = asyncio.to_thread(self._load_checkpoint_state, session_id)
                user_msg_task = asyncio.create_task(
                    self.append_message(
                        session_id,
                        "user",
                        current_query,
                        "QUERY",
                        user_id=user_id,
                        existing_messages=cleaned_messages,
                    )
                )
                (retrieval_chunks, video_suggestions), company_chunks, approved_feedback_memory, checkpoint_state, messages_with_user = await asyncio.gather(
                    course_task, company_task, feedback_task, checkpoint_task, user_msg_task
                )
        else:
            if is_user_social:
                router_decision = {"node_type": "greeting" if is_user_greeting else ("goodbye" if "bye" in current_query.lower() else "thank"), "category": "GREETING" if is_user_greeting else "SOCIAL"}
                retrieval_chunks, video_suggestions = [], []
                company_chunks = []
                approved_feedback_memory = None
                checkpoint_state = self._load_checkpoint_state(session_id)
                messages_with_user = await self.append_message(
                    session_id,
                    "user",
                    current_query,
                    "GREETING" if is_user_greeting else "QUERY",
                    user_id=user_id,
                    existing_messages=cleaned_messages,
                )
            else:
                if on_token:
                    await on_token(get_status_event("searching"))

                # Standalone query is already resolved upstream; run router, course retrieval, company retrieval, feedback memory, checkpoint, and message append in parallel!
                router_task = asyncio.create_task(
                    self.analyzer.classify_for_router(
                        current_query,
                        previous_questions
                    )
                )
                course_task = asyncio.create_task(self._retrieve_chunks(standalone_query))
                company_task = asyncio.create_task(self._run_company_retrieval(standalone_query, current_query, user_profile))
                feedback_task = asyncio.create_task(self._retrieve_approved_feedback_memory(standalone_query, user_profile))
                checkpoint_task = asyncio.to_thread(self._load_checkpoint_state, session_id)
                user_msg_task = asyncio.create_task(
                    self.append_message(
                        session_id,
                        "user",
                        current_query,
                        "QUERY",
                        user_id=user_id,
                        existing_messages=cleaned_messages,
                    )
                )
                router_decision, (retrieval_chunks, video_suggestions), company_chunks, approved_feedback_memory, checkpoint_state, messages_with_user = await asyncio.gather(
                    router_task, course_task, company_task, feedback_task, checkpoint_task, user_msg_task
                )

        if on_token:
            await on_token(get_status_event("analyzing"))

        logger.info(
            f"⚡ [PARALLEL UPSTREAM FINISHED] Completed in {time.perf_counter() - t_upstream_start:.3f}s "
            f"(Course chunks={len(retrieval_chunks)}, Company chunks={len(company_chunks)}, Router node={router_decision.get('node_type')})"
        )

        node_type = router_decision.get("node_type", "").lower()

        if understanding_summary is None:
            if node_type == "query":
                understanding_summary = await self.generate_understanding(
                    standalone_query
                )
            else:
                understanding_summary = ""

        logger.info(f"🧠 Understanding Summary:\n{understanding_summary}\n")

        logger.info("\n🧾 ===== QUERY DEBUG =====")
        logger.info(f"👉 Current Query:\n{current_query}\n")
        logger.info(f"🧠 Rewritten Query:\n{standalone_query}")
        logger.info("===== END DEBUG =====\n")

        is_social = node_type in {"greeting", "goodbye", "thank", "well_wish"}
        is_gap_analysis = (
            node_type in {"gap_analysis_request", "gap_analysis"}
            or router_decision.get("category") == "GAP_ANALYSIS_REQUEST"
            or is_gap_analysis_request(current_query)
            or is_gap_analysis_request(standalone_query)
        )

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
            company_chunks = []
            video_suggestions = []
            checkpoint_state = {}

        elif is_gap_analysis:
            logger.info("⚡ FAST MODE: GAP_ANALYSIS_REQUEST")

            user_category = "GAP_ANALYSIS_REQUEST"
            full_history = cleaned_messages
            history_for_llm = []
            meaningful_history = []
            retrieval_chunks = []
            company_chunks = []
            video_suggestions = []
            checkpoint_state = {}

        # -----------------------------
        # 🧠 NORMAL MODE
        # -----------------------------
        else:
            logger.info(f"🧠 NORMAL MODE: {node_type}")

            if self.session_service and session_id and current_query:
                try:
                    asyncio.create_task(
                        self.session_service.update_session_title(session_id, current_query)
                    )
                except Exception:
                    pass

            user_category = self._normalize_category(
                category or router_decision.get("category"),
                "QUERY",
            )

            full_history = self._clean_messages(messages_with_user)
            history_for_llm = self._convert_messages_for_llm(full_history)

            meaningful_history = checkpoint_state.get("meaningful_history", []) or []
            logger.info(f"[MEMORY] Loaded meaningful_history: {len(meaningful_history)}")

        # -----------------------------
        # 🕵️ SCOPE CONTROL CHECK
        # -----------------------------
        is_out_of_scope = False
        if not is_social and not is_gap_analysis:
            t_scope_start = time.perf_counter()
            scope_decision = await self.check_query_scope(standalone_query, retrieval_chunks)
            logger.info(f"Scope decision: {scope_decision} (checked in {time.perf_counter() - t_scope_start:.3f}s)")
            if scope_decision == "OUT-OF-SCOPE":
                if not is_company_query(standalone_query, user_profile.get("company_name", "")):
                    is_out_of_scope = True
                    retrieval_chunks = []
                    company_chunks = []
                    video_suggestions = []
            elif scope_decision == "MIXED":
                cleaned_query = await self.rewrite_mixed_query(standalone_query)
                standalone_query = cleaned_query
                course_task = asyncio.create_task(self._retrieve_chunks(standalone_query))
                comp_task = asyncio.create_task(self._run_company_retrieval(standalone_query, current_query, user_profile))
                (retrieval_chunks, video_suggestions), company_chunks = await asyncio.gather(course_task, comp_task)
        else:
            retrieval_chunks = []
            company_chunks = []
            video_suggestions = []
            
        video_suggestions = self._normalize_video_suggestions(
            video_suggestions
        )

        # -----------------------------
        # 3️⃣ BUILD STATE
        # -----------------------------
        state = {
            "current_query": current_query,
            "standalone_query": standalone_query,
            "understanding_summary": understanding_summary,
            "previous_questions": previous_questions,
            "retrieval_chunks": retrieval_chunks,
            "company_chunks": company_chunks,
            "video_suggestions": video_suggestions,
            "meaningful_messages": meaningful_history,
            "meaningful_history": meaningful_history,
            "messages": history_for_llm,
            "session_messages": full_history,
            "user_id": user_id,
            "user_profile": user_profile,
            "company_vector_store": self.company_vector_store, 
            "approved_feedback_preference": approved_feedback_memory,
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

        if on_token:
            await on_token(get_status_event("preparing"))

        try:

            if is_gap_analysis:
                logger.info("📑 SMS GAP ANALYSIS INQUIRY DETECTED")
                gap_prompt_content = (
                    "To compare your Safety Management System (SMS) with international maritime industry standards "
                    "(SOLAS, MARPOL, STCW, ISM Code), please upload your SMS document. "
                    "Would you like to upload your document to proceed with the gap analysis?"
                )
                state["node_response"] = {
                    "type": "query",
                    "content": gap_prompt_content,
                    "sections": [
                        {
                            "topic_code": "SMS_GAP_ANALYSIS",
                            "topic_name": "Safety Management System (SMS) Gap Analysis",
                            "content": gap_prompt_content,
                        }
                    ],
                    "chunks_used": [],
                    "videos": [],
                    "images": [],
                    "pdfs": [],
                    "question_suggestions": [
                        "What maritime standards are covered in the gap analysis?",
                        "What file formats are supported (.pdf, .docx)?",
                    ],
                    "metadata": {
                        "category": "GAP_ANALYSIS_REQUEST",
                        "requires_upload": True,
                    }
                }
                if on_token:
                    await on_token({"type": "content", "token": gap_prompt_content})

            elif is_out_of_scope:

                logger.info("🚫 OUT OF SCOPE QUESTION REJECTED")
                out_msg = get_random_out_of_scope_message()

                state["node_response"] = {
                    "type": "query",
                    "content": out_msg,
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
                        "routing_reason": "out_of_scope"
                    }
                }
                if on_token:
                    await on_token({"type": "content", "token": out_msg})

            elif node_type == "greeting":
                state = await greeting_node(state)
                if on_token and state.get("node_response", {}).get("content"):
                    await on_token({"type": "content", "token": state["node_response"]["content"]})

            elif node_type == "goodbye":
                state = await goodbye_node(state)
                if on_token and state.get("node_response", {}).get("content"):
                    await on_token({"type": "content", "token": state["node_response"]["content"]})

            elif node_type == "thank":
                state = await thank_node(state)
                if on_token and state.get("node_response", {}).get("content"):
                    await on_token({"type": "content", "token": state["node_response"]["content"]})

            elif node_type == "well_wish":
                state = await well_wish_node(state)
                if on_token and state.get("node_response", {}).get("content"):
                    await on_token({"type": "content", "token": state["node_response"]["content"]})

            elif node_type == "summary":
                state = await summary_node(state, self.openai_service, self.suggestion_service)
                if on_token and state.get("node_response", {}).get("content"):
                    await on_token({"type": "content", "token": state["node_response"]["content"]})

            elif node_type == "quiz":
                state = await quiz_node(state, self.openai_service, self.suggestion_service)
                if on_token and state.get("node_response", {}).get("content"):
                    await on_token({"type": "content", "token": state["node_response"]["content"]})

            elif node_type == "threadning":
                state = await threadning_node(state)
                if on_token and state.get("node_response", {}).get("content"):
                    await on_token({"type": "content", "token": state["node_response"]["content"]})

            elif node_type == "negative":
                state = await negative_node(state, self.suggestion_service)
                if on_token and state.get("node_response", {}).get("content"):
                    await on_token({"type": "content", "token": state["node_response"]["content"]})

            elif node_type == "query":
                has_company = bool(
                    user_profile.get("company_id")
                    or user_profile.get("company_name")
                    or user_profile.get("CompanyName")
                    or user_profile.get("company")
                )
                t_node_start = time.perf_counter()
                if has_company and state.get("company_chunks"):
                    state = await company_query_node(
                        state,
                        self.openai_service,
                        self.suggestion_service,
                        on_token=on_token,
                    )
                    # If company_query_node returned without populating node_response or company_answer is None, fallback to query_node
                    if not state.get("node_response") or not state["node_response"].get("content") or state.get("company_answer") is None:
                        state = await query_node(
                            state,
                            self.openai_service,
                            self.suggestion_service,
                            self.vector_store,
                            on_token=on_token,
                        )
                else:
                    state = await query_node(
                        state,
                        self.openai_service,
                        self.suggestion_service,
                        self.vector_store,
                        on_token=on_token,
                    )
                logger.info(f"⚡ [LLM Generation] Node '{node_type}' completed in {time.perf_counter() - t_node_start:.3f}s")

            else:
                state = await fallback_node(
                    state,
                    self.suggestion_service,
                    self.openai_service,
                )
                if on_token and state.get("node_response", {}).get("content"):
                    await on_token({"type": "content", "token": state["node_response"]["content"]})

            raw_result = state

        except Exception as e:
            logger.exception(f"❌ Flow execution failed: {e}")
            raise

        node_response = raw_result.get("node_response")
        if not node_response or not isinstance(node_response, dict) or not node_response.get("content"):
            raw_comp = state.get("company_answer")
            if raw_comp and "NO_COMPANY_DATA" not in raw_comp:
                content_val = raw_comp
            else:
                content_val = "I am here to assist with your maritime and company SMS procedures. How can I help you?"

            node_response = {
                "type": "query",
                "content": content_val,
                "sections": [
                    {
                        "topic_code": "MARITIME_QUERY",
                        "topic_name": "Marine Maritime Response",
                        "content": content_val,
                    }
                ],
                "chunks_used": state.get("company_chunks", []) or state.get("retrieval_chunks", []) or [],
                "question_suggestions": self.suggestion_service.generate_from_response(
                    query=current_query,
                    response_text=content_val,
                    chunks=state.get("company_chunks", []) or state.get("retrieval_chunks", []) or [],
                ),
                "videos": state.get("video_suggestions", []) or [],
                "images": state.get("images", []) or [],
                "pdfs": state.get("pdfs", []) or [],
                "metadata": {"category": "QUERY"}
            }

        # Sanitize any accidental internal token leak (e.g. NO_COMPANY_DATA)
        if node_response and isinstance(node_response, dict):
            if "NO_COMPANY_DATA" in str(node_response.get("content", "")):
                node_response["content"] = re.sub(r'NO_COMPANY_DATA\s*', '', str(node_response["content"])).strip()
            if isinstance(node_response.get("sections"), list):
                for sec in node_response["sections"]:
                    if isinstance(sec, dict) and "content" in sec and "NO_COMPANY_DATA" in str(sec["content"]):
                        sec["content"] = re.sub(r'NO_COMPANY_DATA\s*', '', str(sec["content"])).strip()

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

        # Media allowed only for genuine in-scope course/company query responses
        is_media_allowed = (
            node_type == "query"
            and not is_social
            and not is_gap_analysis
            and not is_out_of_scope
            and user_category not in {"GREETING", "GOODBYE", "THANK", "WELL_WISH", "FALLBACK", "GAP_ANALYSIS_REQUEST", "OUT_OF_SCOPE"}
        )

        all_videos = []
        all_images = []
        all_pdfs = []
        all_topic_codes = []

        if is_media_allowed:
            t_media_start = time.perf_counter()
            # Collect active and company chunks
            active_chunks = state.get("retrieval_chunks", []) or retrieval_chunks or []
            company_chunks = state.get("company_chunks", []) or []
            all_chunks = list(active_chunks) + list(company_chunks)

            # Collect videos from all sources
            state_videos = state.get("video_suggestions", []) or []
            node_videos = getattr(validated, "videos", None) or []
            if isinstance(node_videos, list):
                combined_video_sources = state_videos + (video_suggestions or []) + node_videos
            effective_q = standalone_query or current_query
            all_videos = extract_videos(all_chunks, combined_video_sources, query=effective_q)

            node_images = getattr(validated, "images", None) or []
            combined_images = node_images + (state.get("images") or [])
            all_images = extract_images(all_chunks, combined_images, query=effective_q, max_images=6)

            # Parallel fallback database search for matching videos and images if needed
            db_vid_task = None
            db_img_task = None

            if not all_videos and effective_q:
                db_vid_task = asyncio.create_task(search_matching_videos_in_db(effective_q, limit=5))

            if len(all_images) < 3 and effective_q:
                db_img_task = asyncio.create_task(search_matching_images_in_db(effective_q, limit=6))

            if db_vid_task and db_img_task:
                db_vids, db_imgs = await asyncio.gather(db_vid_task, db_img_task)
            elif db_vid_task:
                db_vids = await db_vid_task
                db_imgs = []
            elif db_img_task:
                db_imgs = await db_img_task
                db_vids = []
            else:
                db_vids, db_imgs = [], []

            if db_vids:
                all_videos = db_vids

            if db_imgs:
                seen_img_keys = {
                    (img.get("id") or img.get("title") or img.get("url") or "").strip().lower()
                    for img in all_images
                }
                for img in db_imgs:
                    k = (img.get("id") or img.get("title") or img.get("url") or "").strip().lower()
                    if k and k not in seen_img_keys:
                        seen_img_keys.add(k)
                        all_images.append(img)

            # Process and cache images, deduplicate, and attach embedded base64 data
            if all_images:
                try:
                    all_images = await ImageManager.process_and_cache_images(all_images, max_images=6)
                except Exception as e:
                    logger.debug(f"Image processing and caching failed: {e}")

            seen_pdfs = set()
            for chunk in all_chunks:
                for pdf in chunk.get("pdfs", []):
                    key = pdf.get("id") or pdf.get("url") or pdf.get("Url") or pdf.get("Link") or pdf.get("link")
                    if not key or key in seen_pdfs:
                        continue
                    seen_pdfs.add(key)
                    all_pdfs.append(pdf)

            node_pdfs = getattr(validated, "pdfs", None) or []
            for pdf in node_pdfs:
                key = pdf.get("id") or pdf.get("url") or pdf.get("Url") or pdf.get("Link") or pdf.get("link")
                if key and key not in seen_pdfs:
                    seen_pdfs.add(key)
                    all_pdfs.append(pdf)

            for chunk in all_chunks:
                topic_code = chunk.get("topic_code")
                if topic_code and topic_code not in all_topic_codes:
                    all_topic_codes.append(topic_code)

            logger.info(f"⚡ [Media Enrichment] Completed in {time.perf_counter() - t_media_start:.3f}s")

        state["messages"] = updated_messages
        self._last_state = state

        logger.info(
            f"✅ [CHAT PIPELINE TOTAL] Total run_chat duration: {time.perf_counter() - t_chat_total_start:.3f}s"
        )

        return (
            validated,
            final_cleaned_history,
            standalone_query,
            understanding_summary,
            {
                "videos": all_videos,
                "images": all_images,
                "pdfs": all_pdfs,
                "topic_codes": all_topic_codes,
                "company_answer": state.get("company_answer"),
            }
        )
