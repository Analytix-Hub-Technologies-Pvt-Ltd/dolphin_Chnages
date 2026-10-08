from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import time

from loguru import logger
from pydantic import BaseModel

from graph.build_graph import build_graph
from pipeline.company_retrieval import company_retrieval_node
from retrieval.faiss_store import DEFAULT_TOP_K, FAISSStore
from retrieval.postgres_loader import PostgresLoader
from services.embedding_config import EMBEDDING_DIM
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService
from services.query_analyzer import (
    EnhancedQueryAnalyzer,
    is_simple_social_intent,
    is_greeting_query,
    extract_name,
)
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
from services.pdf_service import pdf_service
from pipeline.company_query import company_query_node
from services.maritime_acronyms import (
    find_acronyms_in_query,
    get_acronym_expansion,
    GENERIC_MARITIME_WORDS,
    expand_query_terms_for_media,
    has_conflicting_acronym,
)
from services.off_topic_detector import (
    is_off_topic_query,
    is_marine_domain_query,
    is_obvious_marine_query,
)

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


def normalize_image_url(url: str) -> str:
    """Normalize image URL, preserving data URIs and properly resolving /storage/ paths."""
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if not url:
        return ""
    if url.startswith("data:"):
        return url

    match = re.search(r'(/storage/(?:images|pdf_images)/[^\s?]+)', url, re.IGNORECASE)
    if match:
        storage_path = match.group(1)
        configured_base = (settings.image_base_url or "").rstrip("/")
        if configured_base:
            return f"{configured_base}{storage_path}"
        return storage_path

    return url



from services.off_topic_detector import (
    is_off_topic_query,
    OFF_TOPIC_KEYWORDS,
    is_marine_domain_query,
    is_obvious_marine_query,
)


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
    """Async wrapper that embeds queries then searches the underlying FAISS store with BM25 hybrid keyword search."""

    def __init__(self, embedder: EmbeddingService, store: FAISSStore, bm25_store=None) -> None:
        self.embedder = embedder
        self.store = store
        self._bm25_store = bm25_store
    
    def get_all_topic_names(self) -> List[str]:
        """
        GENERIC: Get all topic names from the underlying FAISS store.
        Delegates to store.get_all_topic_names() for dynamic acronym loading.
        """
        return self.store.get_all_topic_names()

    def _get_bm25(self):
        if self._bm25_store is not None:
            return self._bm25_store
        try:
            from api.dependencies import get_bm25_store
            self._bm25_store = get_bm25_store()
        except Exception as e:
            logger.debug(f"BM25 store unavailable: {e}")
        return self._bm25_store

    async def search_with_embeddings(
            self,
            query: str,
            k: int = DEFAULT_TOP_K
    ) -> List[Dict[str, Any]]:
        """
        Search using the embedder to generate vectors before querying FAISS,
        and blend with BM25 exact keyword search using Reciprocal Rank Fusion (RRF).
        """
        if not query or not query.strip():
            logger.warning("Empty query provided to VectorStoreAdapter")
            return []

        # Fast check: If FAISS index is empty and BM25 is empty, return immediately without embedding
        if hasattr(self.store, "index") and (self.store.index is None or getattr(self.store.index, "ntotal", 0) == 0):
            bm25 = self._get_bm25()
            if not bm25 or not getattr(bm25, "is_indexed", False) or getattr(bm25, "corpus_size", 0) == 0:
                logger.info("⚡ Vector store is empty, skipping search")
                return []

        try:
            cleaned_query = query.strip()
            query_vector = await self.embedder.embed_query(query)
            if len(query_vector) != EMBEDDING_DIM:
                logger.error("Embedding dimension mismatch. Expected {}, got {}", EMBEDDING_DIM, len(query_vector))
                raise ValueError(
                    f"Embedding dimension mismatch. "
                    f"Expected {EMBEDDING_DIM}, got {len(query_vector)}"
                )

            # 1. FAISS Dense Search
            faiss_results: List[Dict[str, Any]] = []
            if hasattr(self.store, "search"):
                faiss_results = self.store.search(query_vector, k=k)
            elif hasattr(self.store, "search_with_embeddings"):
                maybe_result = self.store.search_with_embeddings(cleaned_query, k=k)
                faiss_results = await maybe_result if asyncio.iscoroutine(maybe_result) else maybe_result

            # 2. BM25 Sparse Keyword Search
            bm25_results: List[Dict[str, Any]] = []
            bm25 = self._get_bm25()
            if bm25 and hasattr(bm25, "search"):
                try:
                    bm25_results = bm25.search(cleaned_query, k=k)
                except Exception as bm_err:
                    logger.warning(f"BM25 search failed: {bm_err}")

            if not bm25_results:
                logger.info(f"✅ FAISS-only search returned {len(faiss_results)} results")
                return faiss_results or []

            # 3. Reciprocal Rank Fusion (RRF)
            rrf_k = 60
            doc_scores: Dict[str, float] = defaultdict(float)
            doc_map: Dict[str, Dict[str, Any]] = {}

            def _doc_key(doc: Dict[str, Any], default_idx: int) -> str:
                return str(doc.get("content_id") or doc.get("topic_name") or f"doc_{default_idx}")

            for rank, doc in enumerate(faiss_results):
                key = _doc_key(doc, rank)
                doc_scores[key] += 1.0 / (rrf_k + rank + 1)
                doc_map[key] = doc

            for rank, doc in enumerate(bm25_results):
                key = _doc_key(doc, rank + 1000)
                doc_scores[key] += 1.0 / (rrf_k + rank + 1)
                if key not in doc_map:
                    doc_map[key] = doc

            # Sort fused results
            sorted_keys = sorted(doc_scores.keys(), key=lambda k_val: doc_scores[k_val], reverse=True)[:k]
            fused_results = []
            for rank, key in enumerate(sorted_keys):
                merged_doc = dict(doc_map[key])
                merged_doc["_rrf_score"] = doc_scores[key]
                merged_doc["_rank"] = rank
                fused_results.append(merged_doc)

            logger.info(f"✅ Hybrid search (FAISS + BM25) returned {len(fused_results)} fused results")
            return fused_results

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
            bm25_store = None,
    ) -> None:
        from api.dependencies import get_company_store, get_transcribe_store, get_bm25_store

        if transcribe_store is None:
            transcribe_store = get_transcribe_store()

        if company_store is None:
            company_store = get_company_store()

        if bm25_store is None:
            try:
                bm25_store = get_bm25_store()
            except Exception as e:
                logger.debug(f"BM25 initialization deferred: {e}")
                bm25_store = None

        self.transcribe_vector_store = VectorStoreAdapter(
            embedder,
            transcribe_store,
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
        self.vector_store = VectorStoreAdapter(embedder, store, bm25_store=bm25_store)
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
                msg.get("message_id", 0)
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
                "videos",
                list(metadata.get("videos") or []),
            )
            new_message.setdefault(
                "images",
                list(metadata.get("images") or []),
            )
            new_message.setdefault(
                "pdfs",
                list(metadata.get("pdfs") or []),
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

        if value is None:
            return []

        if isinstance(value, list):
            return [v for v in value if isinstance(v, dict)]

        if isinstance(value, dict):
            return [value]

        if isinstance(value, (str, bytes)):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [v for v in parsed if isinstance(v, dict)]
                if isinstance(parsed, dict):
                    return [parsed]
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

        images = self.image_service.get_images_by_topic_code(topic_code)
        if not images:
            images = self._coerce_media(raw.get("topic_image") or raw.get("images"))

        return {
            "content_id": raw.get("content_id") or raw.get("id"),
            "course_code": str(raw.get("course_code") or "").strip(),
            "topic_name": topic_name,
            "topic_code": topic_code,
            "topic_content": topic_content,
            "content": combined_content,
            "videos": self._coerce_media(raw.get("topic_video") or raw.get("videos")),
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

        logger.debug(
            "Video suggestions built",
            suggestion_count=len(suggestions),
        )
        return self._normalize_video_suggestions(suggestions)

    async def _filter_and_rank_images(
        self,
        chunks: List[Dict[str, Any]],
        query: str = "",
        max_images: int = 5,
        context_chunks: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Filter out broken, noisy, or unreadable PDF scraps, prioritize clear relevant topic photos that exist or can be cached on disk."""
        query_clean = (query or "").lower().strip()
        from services.maritime_acronyms import expand_query_terms_for_media, COMMON_ENGLISH_STOPWORDS
        effective_query_words = expand_query_terms_for_media(query, (context_chunks or []) + (chunks or []))

        # Extract 2-word phrase ngrams from query for exact matching (exclude English stopwords so phrases like 'different types' never match)
        content_words = [w for w in re.findall(r'\b[a-zA-Z]{3,}\b', query_clean) if w not in COMMON_ENGLISH_STOPWORDS]
        bigrams = [" ".join(content_words[i:i+2]) for i in range(len(content_words) - 1)]

        candidates = []
        seen_keys = set()

        for chunk_idx, chunk in enumerate(chunks or []):
            topic_name = str(chunk.get("topic_name") or chunk.get("title") or "").strip().lower()
            raw_images = chunk.get("images") or chunk.get("topic_image") or []
            if not isinstance(raw_images, list):
                continue

            for img in raw_images:
                if not isinstance(img, dict):
                    continue

                raw_url = str(
                    img.get("Url") or img.get("url") or img.get("image_url") or img.get("imageUrl") or img.get("path") or ""
                ).strip()
                base64_val = str(img.get("base64") or img.get("Base64") or "").strip()
                img_id = str(img.get("Id") or img.get("id") or "").strip().lower()

                # Discard completely empty or null URLs without base64 or img_id
                if not raw_url and not base64_val and not img_id:
                    continue
                if raw_url.lower() in ("none", "null", "undefined", "") and not base64_val and not img_id:
                    continue

                # Normalize URL: fix accidental double slashes in paths like https://domain//storage
                norm_url = re.sub(r'(?<!:)/{2,}', '/', raw_url)

                title = str(img.get("Title") or img.get("title") or img.get("name") or "").strip()
                about = str(img.get("About") or img.get("about") or "").strip()
                combined_text = f"{title} {about} {topic_name}".lower()

                # Deduplicate by unique image ID or normalized filename
                if img_id and img_id not in ("none", "null", ""):
                    key = img_id
                else:
                    fname_match = norm_url.split("/")[-1].split("?")[0].strip().lower()
                    key = fname_match if fname_match else norm_url.lower()

                if not key or key in seen_keys:
                    continue
                seen_keys.add(key)

                # Discard image if candidate text contains a conflicting maritime acronym
                from services.maritime_acronyms import has_conflicting_acronym, find_acronyms_in_query, get_acronym_expansion
                if has_conflicting_acronym(query, f"{title} {about} {topic_name}"):
                    continue

                # Strict acronym alignment: If the query asks about a specific acronym (e.g. ECDIS, SOLAS, ARPA, MARPOL),
                # the image MUST mention the acronym or its expansion in its title, about, or topic.
                query_acronyms = find_acronyms_in_query(query)
                if query_acronyms:
                    has_acr_match = False
                    for acr in query_acronyms:
                        acr_lower = acr.lower()
                        if re.search(rf'\b{re.escape(acr_lower)}\b', combined_text):
                            has_acr_match = True
                            break
                        for exp in get_acronym_expansion(acr):
                            if exp.lower() in combined_text:
                                has_acr_match = True
                                break
                        if has_acr_match:
                            break
                    if not has_acr_match:
                        continue

                # Determine if image is a PDF scrap/manual page extraction
                is_pdf_scrap = (
                    "/storage/pdf_images/" in norm_url.lower()
                    or "_img_" in norm_url.lower()
                    or norm_url.lower().startswith("pdf_")
                )

                # Filter out raw manual page fragments (e.g., from manuals/checklists with generic document title)
                if is_pdf_scrap:
                    if any(w in combined_text for w in [
                        "guide", "manual", "checklist", "handbook", "plan - sample", "response plan",
                        "form", "permit", "procedure", "appendix", "annex", "code of conduct", "conduct", "circular", "notice"
                    ]):
                        continue
                    if not title or len(title.strip()) < 3 or title.lower() in ("image", "none", "null", "untitled", "figure", "page", "table"):
                        if not about or len(about.strip()) < 10:
                            continue

                # Base score prioritizes earlier chunks
                score = 100.0 - (chunk_idx * 5.0)

                # Real photos / uploaded diagrams get priority over raw PDF clips
                if not is_pdf_scrap:
                    score += 40.0

                # Exact phrase matching boost (+120 for title match, +60 for topic match)
                has_exact_phrase_in_title = any(bg in title.lower() for bg in bigrams if len(bg) > 6)
                has_exact_phrase_in_topic = any(bg in topic_name for bg in bigrams if len(bg) > 6)
                has_exact_phrase = has_exact_phrase_in_title or has_exact_phrase_in_topic
                if has_exact_phrase_in_title:
                    score += 120.0
                elif has_exact_phrase_in_topic:
                    score += 60.0

                # Keyword relevance boost (with stemming support)
                match_count = 0
                for qw in effective_query_words:
                    qw_stem = re.sub(r'(ing|tion|tions|ed|es|s)$', '', qw)
                    stem = qw_stem if len(qw_stem) >= 3 else qw
                    if qw in title.lower() or stem in title.lower():
                        match_count += 1
                        score += 35.0
                    elif qw in topic_name or stem in topic_name:
                        match_count += 1
                        score += 25.0
                    elif qw in about.lower() or stem in about.lower():
                        if not title or title.lower() in ("image", "none", "null", "untitled", "figure", "page", "table", ""):
                            match_count += 1
                        score += 15.0

                is_primary_chunk = (chunk_idx == 0 and not chunk.get("_is_sme_approved"))
                if is_primary_chunk:
                    score += 20.0

                # Match against retrieved topic names
                eval_chunks = (context_chunks or []) + (chunks or [])
                matches_retrieved_topic = False
                for chk in eval_chunks[:5]:
                    c_topic = str(chk.get("topic_name") or chk.get("title") or "").lower().strip()
                    c_clean = re.sub(r'^\s*[\d\.\-\s]+', '', c_topic).strip()
                    if c_clean and len(c_clean) >= 4:
                        if c_clean in title.lower() or c_clean in topic_name:
                            matches_retrieved_topic = True
                            match_count += 3
                            score += 150.0
                            break

                # Discard image if candidate has a specific title with zero match to effective query words and no exact phrase in title
                title_has_match = any(qw in title.lower() or (len(qw) >= 4 and re.sub(r'(ing|tion|tions|ed|es|s)$', '', qw) in title.lower()) for qw in effective_query_words)
                is_generic_title = not title or title.lower() in ("image", "none", "null", "untitled", "figure", "page", "table", "reference image")
                if not is_generic_title and not title_has_match and not has_exact_phrase_in_title and not matches_retrieved_topic:
                    continue

                # Strict relevance: EVERY image must have at least one keyword match or exact phrase.
                # Remove primary chunk immunity so irrelevant diagrams are never forced.
                if effective_query_words and match_count == 0 and not has_exact_phrase and not matches_retrieved_topic:
                    continue

                # Authentic title if missing or overly generic (never use generic "Reference Image")
                display_title = title
                if not display_title or display_title.lower() in ("image", "none", "null", "untitled", "reference image"):
                    display_title = about if (about and len(about) < 60) else (chunk.get("topic_name") or "Image")
                elif display_title.lower().startswith(("figure", "fig.", "fig ", "photo", "pic ", "pic.")):
                    if about and 4 <= len(about) <= 80:
                        display_title = about
                    elif chunk.get("topic_name"):
                        display_title = f"{chunk.get('topic_name')} - {display_title}"

                cleaned_img = {
                    **img,
                    "Title": display_title,
                    "title": display_title,
                    "Url": norm_url,
                    "url": norm_url,
                }
                candidates.append((score, match_count, not is_pdf_scrap, cleaned_img))

        candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)

        # Asynchronously verify and cache the top candidate images to ensure none are broken
        top_candidates = [item[3] for item in candidates[:max_images * 2]]
        if not top_candidates:
            return []

        # 1. Fast local disk check in rank order (no network I/O)
        resolved_urls: List[Optional[str]] = [
            self.image_service.get_local_cached_url(img) for img in top_candidates
        ]

        # 2. Only fetch remote images if local verified count is below max_images
        verified_count = sum(1 for u in resolved_urls if u is not None)
        if verified_count < max_images:
            remote_tasks = []
            remote_indices = []
            for idx, (img, u) in enumerate(zip(top_candidates, resolved_urls)):
                if u is None:
                    remote_tasks.append(self.image_service.ensure_image_cached(img))
                    remote_indices.append(idx)
                    if len(remote_tasks) >= (max_images * 2 - verified_count):
                        break

            if remote_tasks:
                try:
                    fetched_results = await asyncio.gather(*remote_tasks, return_exceptions=True)
                    for idx, res in zip(remote_indices, fetched_results):
                        if isinstance(res, str) and res.strip():
                            resolved_urls[idx] = res.strip()
                except Exception as e:
                    logger.debug(f"Error during remote image verification: {e}")

        verified_images = []
        for img, res in zip(top_candidates, resolved_urls):
            if isinstance(res, str) and res.strip():
                verified_img = {
                    **img,
                    "Url": res.strip(),
                    "url": res.strip(),
                }
                verified_images.append(verified_img)
                if len(verified_images) >= max_images:
                    break

        return verified_images[:max_images]

    def _build_sibling_search_patterns(self, query: str, primary_chunk: Any) -> List[str]:
        """Build high-precision SQL ILIKE search patterns based on maritime acronyms, expansions, and topic words."""
        from services.maritime_acronyms import (
            find_acronyms_in_query,
            get_acronym_expansion,
            GENERIC_MARITIME_WORDS,
            COMMON_ENGLISH_STOPWORDS,
        )
        stop_words = COMMON_ENGLISH_STOPWORDS | GENERIC_MARITIME_WORDS | {
            "requirements", "requirement", "regulation", "regulations", "water"
        }

        patterns = []

        # 1. Acronyms & their expansions from the query
        detected_acronyms = find_acronyms_in_query(query)
        for acr in detected_acronyms:
            patterns.append(f"%{acr}%")
            for exp in get_acronym_expansion(acr):
                if len(exp) >= 4 and exp.lower() not in GENERIC_MARITIME_WORDS:
                    patterns.append(f"%{exp}%")

        # 2. Topic names from top retrieved chunks (primary + first few siblings)
        candidate_chunks = primary_chunk if isinstance(primary_chunk, list) else ([primary_chunk] if primary_chunk else [])
        for chk in candidate_chunks[:5]:
            topic_name = str((chk or {}).get("topic_name") or (chk or {}).get("title") or "").strip()
            if topic_name and len(topic_name) > 3:
                clean_topic = re.sub(r'[\(\)\[\]\{\}\<\>_]', ' ', topic_name)
                # Strip leading numbering like '1. ', '1.2.3 '
                clean_topic = re.sub(r'^\s*[\d\.\-\s]+', '', clean_topic).strip()
                if len(clean_topic) >= 4:
                    patterns.append(f"%{clean_topic}%")
                    for acr in find_acronyms_in_query(clean_topic):
                        patterns.append(f"%{acr}%")
                        for exp in get_acronym_expansion(acr):
                            if len(exp) >= 4 and exp.lower() not in GENERIC_MARITIME_WORDS:
                                patterns.append(f"%{exp}%")

        # 3. Query bigrams (high precision 2-word phrases, e.g. 'merchant ships', 'auxiliary boiler')
        q_clean = (query or "").lower()
        content_words = [w for w in re.findall(r'\b[a-zA-Z]{3,}\b', q_clean) if w not in COMMON_ENGLISH_STOPWORDS]
        query_bigrams = [" ".join(content_words[i:i+2]) for i in range(len(content_words) - 1)]
        for bg in query_bigrams:
            if len(bg) > 6:
                patterns.append(f"%{bg}%")

        # For queries specifically asking about ship types or merchant ships, include primary vessel categories
        is_ship_type_q = any(phrase in q_clean for phrase in [
            "types of ship", "types of merchant ship", "ship type", "types of vessel",
            "kind of ship", "classification of ship"
        ]) or ("merchant" in q_clean and any(w in q_clean for w in ["ship", "ships", "vessel", "vessels"]))
        if is_ship_type_q:
            patterns.extend([
                "%Ship Types%",
                "%Types of Ships%",
                "%Container Ships%",
                "%Types of Oil Tankers%",
                "%General Cargo ships%",
                "%Chemical Tankers%",
                "%Bulk Carrier%",
            ])

        # 4. Fallback to distinctive query keywords only if no specific topic/acronym/phrase patterns exist
        if not patterns:
            for w in content_words:
                if w not in stop_words:
                    patterns.append(f"%{w}%")

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for p in patterns:
            p_lower = p.lower()
            if p_lower not in seen and len(p_lower) > 3:
                seen.add(p_lower)
                deduped.append(p)

        return deduped[:12]

    def _build_exact_video_search_patterns(self, query: str, chunks: List[Dict[str, Any]] = None) -> List[str]:
        """Extract high-precision exact video title search patterns (e.g. acronym and its primary expansion, chunk topics)."""
        from services.maritime_acronyms import (
            find_acronyms_in_query,
            get_acronym_expansion,
            GENERIC_MARITIME_WORDS,
        )
        detected_acrs = find_acronyms_in_query(query)
        exact_patterns = []
        for acr in detected_acrs:
            expansions = get_acronym_expansion(acr)
            if expansions:
                primary_exp = expansions[0]
                if len(primary_exp) >= 4 and primary_exp.lower() not in GENERIC_MARITIME_WORDS:
                    exact_patterns.append(f"%{primary_exp}%")
            if len(acr) >= 3:
                exact_patterns.append(f"% {acr} %")
                exact_patterns.append(f"%({acr})%")
                exact_patterns.append(f"% {acr}")
                exact_patterns.append(f"{acr} %")

        clean_q = re.sub(
            r'^(please\s+explain(\s+me)?|explain(\s+me)?|what\s+is(\s+the)?|what\s+are(\s+the)?|what\s+are|tell\s+me(\s+about)?|how\s+does|show\s+me|describe|overview\s+of|give\s+me(\s+an?\s+overview\s+of)?)\s+',
            '',
            (query or "").strip(),
            flags=re.IGNORECASE,
        ).rstrip("?").strip()
        if len(clean_q) >= 4 and f"%{clean_q}%" not in exact_patterns:
            exact_patterns.append(f"%{clean_q}%")

        # Include cleaned topic names from top retrieved chunks
        for chk in (chunks or [])[:3]:
            t_name = str((chk or {}).get("topic_name") or (chk or {}).get("title") or "").strip()
            t_clean = re.sub(r'^\s*[\d\.\-\s]+', '', t_name).strip()
            if len(t_clean) >= 4 and f"%{t_clean}%" not in exact_patterns:
                exact_patterns.append(f"%{t_clean}%")

        q_clean = (query or "").lower()
        is_ship_type_q = any(phrase in q_clean for phrase in [
            "types of ship", "types of merchant ship", "ship type", "types of vessel",
            "kind of ship", "classification of ship"
        ]) or ("merchant" in q_clean and any(w in q_clean for w in ["ship", "ships", "vessel", "vessels"]))
        if is_ship_type_q:
            exact_patterns.extend([
                "%Ship Types%",
                "%Types of Container Ships%",
                "%General Cargo Ships%",
                "%Container Ships%",
            ])

        seen = set()
        deduped = []
        for p in exact_patterns:
            if p.lower() not in seen:
                seen.add(p.lower())
                deduped.append(p)
        return deduped[:8]

    async def _find_sibling_images(
        self,
        chunks: List[Dict[str, Any]],
        query: str = "",
        max_images: int = 5,
        db_timings: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Look up related course_content rows in DB for this topic that have images when retrieved chunks lack images."""
        if not chunks and not query:
            return []

        try:
            search_patterns = self._build_sibling_search_patterns(query, chunks)
            topic_codes = [c.get("topic_code") for c in (chunks or []) if c.get("topic_code")]

            if not search_patterns and not topic_codes:
                return []

            q_clean = (query or "").lower()
            is_ship_type_q = any(phrase in q_clean for phrase in [
                "types of ship", "types of merchant ship", "ship type", "types of vessel",
                "kind of ship", "classification of ship"
            ]) or ("merchant" in q_clean and any(w in q_clean for w in ["ship", "ships", "vessel", "vessels"]))

            t_db0 = time.perf_counter()
            pool = await get_pool()
            async with pool.acquire() as conn:
                if is_ship_type_q:
                    rows = await conn.fetch(
                        """
                        SELECT content_id, topic_name, topic_code, topic_image
                        FROM course_content
                        WHERE (
                            (cardinality($1::text[]) > 0 AND topic_name ILIKE ANY($1::text[]))
                            OR (cardinality($2::text[]) > 0 AND topic_code = ANY($2::text[]))
                        )
                        AND topic_image IS NOT NULL
                        AND jsonb_array_length(topic_image) > 0
                        AND topic_name NOT ILIKE '%fire%'
                        AND topic_name NOT ILIKE '%pollution%'
                        AND topic_name NOT ILIKE '%garbage%'
                        AND topic_name NOT ILIKE '%psc%'
                        ORDER BY 
                            CASE 
                                WHEN topic_name ILIKE 'Types of Merchant Ships%' THEN 0
                                WHEN topic_name ILIKE 'Ship Types%' OR topic_name ILIKE '1. Ship Types%' THEN 1
                                WHEN topic_name ILIKE 'Container Ships%' THEN 2
                                WHEN topic_name ILIKE 'Types of Oil Tankers%' THEN 3
                                WHEN topic_name ILIKE 'General Cargo ships%' THEN 4
                                WHEN cardinality($1::text[]) > 0 AND topic_name ILIKE ANY($1::text[]) THEN 5
                                ELSE 6
                            END,
                            content_id ASC
                        LIMIT 15
                        """,
                        search_patterns,
                        topic_codes[:5]
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT content_id, topic_name, topic_code, topic_image
                        FROM course_content
                        WHERE (
                            (cardinality($1::text[]) > 0 AND topic_name ILIKE ANY($1::text[]))
                            OR (cardinality($2::text[]) > 0 AND topic_code = ANY($2::text[]))
                        )
                        AND topic_image IS NOT NULL
                        AND jsonb_array_length(topic_image) > 0
                        ORDER BY 
                            CASE WHEN cardinality($1::text[]) > 0 AND topic_name ILIKE ANY($1::text[]) THEN 0 ELSE 1 END,
                            content_id ASC
                        LIMIT 15
                        """,
                        search_patterns,
                        topic_codes[:5]
                    )
            if db_timings is not None:
                db_timings["db_query"] = db_timings.get("db_query", 0.0) + (time.perf_counter() - t_db0)

            if not rows:
                return []

            sibling_chunks = []
            for r in rows:
                c_dict = dict(r)
                sibling_chunks.append({
                    "topic_name": c_dict.get("topic_name"),
                    "topic_code": c_dict.get("topic_code"),
                    "images": self._coerce_media(c_dict.get("topic_image")),
                })

            return await self._filter_and_rank_images(
                sibling_chunks, query=query, max_images=max_images, context_chunks=chunks
            )

        except Exception as e:
            logger.debug(f"Failed to find sibling images: {e}")
            return []

    def _filter_and_rank_videos(
        self,
        chunks: List[Dict[str, Any]],
        video_suggestions: List[Dict[str, Any]],
        query: str = "",
        max_videos: int = 5,
        context_chunks: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Filter out broken video links, deduplicate, and prioritize specific relevant videos over generic intro videos."""
        query_clean = (query or "").lower().strip()
        from services.maritime_acronyms import expand_query_terms_for_media, has_conflicting_acronym, COMMON_ENGLISH_STOPWORDS
        effective_query_words = expand_query_terms_for_media(query, (context_chunks or []) + (chunks or []))
        query_asked_intro = any(w in query_clean for w in ["intro", "introduction", "overview", "basics", "summary"])

        # Extract 2-word phrase ngrams from query for exact matching (exclude English stopwords so phrases like 'different types' never match)
        content_words = [w for w in re.findall(r'\b[a-zA-Z]{3,}\b', query_clean) if w not in COMMON_ENGLISH_STOPWORDS]
        bigrams = [" ".join(content_words[i:i+2]) for i in range(len(content_words) - 1)]

        candidates = []
        seen = set()

        def process_video(video, chunk_rank=0, default_title="Course video", topic_name=""):
            if not isinstance(video, dict):
                return
            extract = lambda keys, d: next((d[k] for k in keys if k in d), "")
            raw_url = str(extract(["url", "Url", "videourl", "videolink", "Link"], video)).strip()
            video_id = str(extract(["video_id", "Id", "id"], video)).strip()

            # Discard broken video URLs
            if not raw_url or raw_url.lower() in ("none", "null", "undefined", ""):
                return
            if not (raw_url.startswith("http://") or raw_url.startswith("https://") or raw_url.endswith(".mp4")):
                return

            v_key = video_id.lower() if video_id else normalize_video_url(raw_url)
            if not v_key or v_key in seen:
                return
            seen.add(v_key)

            title_raw = extract(["Title", "title"], video)
            if not title_raw:
                title_raw = extract(["About"], video)
                if title_raw:
                    title_raw = re.sub(r'<[^>]+>', '', str(title_raw))
            title = str(title_raw).strip() if title_raw else default_title
            thumbnail = str(extract(["Thumbnail", "thumbnail"], video)).strip()

            # Discard video if candidate text contains a conflicting maritime acronym
            if has_conflicting_acronym(query, f"{title} {topic_name}"):
                return

            lower_title = title.lower()
            combined_text = f"{lower_title} {topic_name.lower()}".strip()
            is_intro = any(w in lower_title for w in ["introduction", "intro to", "overview", "course overview", "welcome", "module overview"])

            score = 100.0 - (chunk_rank * 5.0)

            # Check keyword relevance in video title and topic with stemming
            match_count = 0
            for qw in effective_query_words:
                qw_stem = re.sub(r'(ing|tion|tions|ed|es|s)$', '', qw)
                stem = qw_stem if len(qw_stem) >= 3 else qw
                if qw in lower_title or stem in lower_title:
                    match_count += 1
                elif qw in topic_name.lower() or stem in topic_name.lower():
                    match_count += 1

            # Match against top retrieved chunk topic names (e.g. topic 'Ship Types' matching video 'Ship Types')
            eval_chunks = (context_chunks or []) + (chunks or [])
            matches_retrieved_topic = False
            for chk in eval_chunks[:5]:
                c_topic = str(chk.get("topic_name") or chk.get("title") or "").lower().strip()
                c_clean = re.sub(r'^\s*[\d\.\-\s]+', '', c_topic).strip()
                if c_clean and len(c_clean) >= 4:
                    if c_clean in lower_title or (len(lower_title) >= 4 and lower_title in c_clean):
                        matches_retrieved_topic = True
                        match_count += 3
                        score += 150.0
                        break

            # Exact phrase match
            has_exact_phrase = any(bg in lower_title for bg in bigrams if len(bg) > 6)
            has_combined_phrase = any(bg in combined_text for bg in bigrams if len(bg) > 6)

            # If it's a generic introduction/overview video, and the query did NOT ask for intro, and no keywords match: DISCARD!
            if is_intro and match_count == 0 and not query_asked_intro:
                return

            # If video has a specific title, require its title to match query keywords, exact phrase, or retrieved topic
            title_has_kw_match = any(qw in lower_title or (len(qw) >= 4 and re.sub(r'(ing|tion|tions|ed|es|s)$', '', qw) in lower_title) for qw in effective_query_words)
            is_generic_vid_title = not title or lower_title in ("course video", "video", "none", "null", "untitled")
            if not is_generic_vid_title and not title_has_kw_match and not has_exact_phrase and not matches_retrieved_topic:
                return

            # Exclude completely unrelated videos when effective query words exist
            if effective_query_words and match_count == 0 and not has_exact_phrase and not has_combined_phrase:
                return

            score += match_count * 30.0
            if has_exact_phrase or has_combined_phrase:
                score += 100.0

            # Direct acronym or primary definition match in video title gets highest priority
            detected_acrs = find_acronyms_in_query(query)
            for acr in detected_acrs:
                if re.search(r'\b' + re.escape(acr) + r'\b', title, flags=re.I):
                    score += 250.0
                    break
                expansions = get_acronym_expansion(acr)
                if expansions:
                    primary_exp = expansions[0]
                    if len(primary_exp) >= 6 and primary_exp.lower() in lower_title:
                        score += 300.0
                        break
                for exp in (expansions[1:] if expansions else []):
                    if len(exp) >= 6 and exp.lower() in lower_title:
                        score += 50.0
                        break

            if is_intro:
                score -= 20.0

            candidates.append((score, match_count, not is_intro, {
                "title": title,
                "url": raw_url,
                "videourl": raw_url,
                "video_id": video_id,
                "thumbnail": thumbnail,
            }))

        for chunk_idx, chunk in enumerate(chunks or []):
            t_name = str(chunk.get("topic_name") or chunk.get("title") or "")
            for v in (chunk.get("videos", []) or chunk.get("topic_video", [])):
                process_video(v, chunk_rank=chunk_idx, default_title=t_name or "Course video", topic_name=t_name)

        for v in (video_suggestions or []):
            process_video(v, chunk_rank=len(chunks) + 1, default_title="Course video", topic_name="")

        candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
        return [c[3] for c in candidates[:max_videos]]

    async def _find_sibling_videos(
        self,
        chunks: List[Dict[str, Any]],
        query: str = "",
        max_videos: int = 5,
        db_timings: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Look up related course_content rows and direct video matches in DB when retrieved chunks lack videos."""
        if not chunks and not query:
            return []

        try:
            q_clean = (query or "").lower()
            is_ship_type_q = any(phrase in q_clean for phrase in [
                "types of ship", "types of merchant ship", "ship type", "types of vessel",
                "kind of ship", "classification of ship"
            ]) or ("merchant" in q_clean and any(w in q_clean for w in ["ship", "ships", "vessel", "vessels"]))

            search_patterns = self._build_sibling_search_patterns(query, chunks)
            exact_video_patterns = self._build_exact_video_search_patterns(query, chunks)
            topic_codes = [c.get("topic_code") for c in (chunks or []) if c.get("topic_code")]

            if not search_patterns and not topic_codes and not exact_video_patterns:
                return []

            t_db0 = time.perf_counter()
            pool = await get_pool()
            direct_videos = []
            seen_urls = set()

            async with pool.acquire() as conn:
                # 1. Tier 1: Search transcribe table for exact video title matches (fast, ~0.05s)
                if exact_video_patterns:
                    try:
                        transcribe_rows = await conn.fetch(
                            """
                            SELECT video_id, video_title, video_link, video_thumbnail
                            FROM transcribe
                            WHERE video_title ILIKE ANY($1)
                            ORDER BY 
                                CASE 
                                    WHEN video_title ILIKE 'Ship Types' THEN 0
                                    WHEN video_title ILIKE 'Types of Container Ships' THEN 1
                                    WHEN video_title ILIKE 'General Cargo Ships' THEN 2
                                    ELSE 3
                                END
                            LIMIT $2
                            """,
                            exact_video_patterns,
                            max_videos,
                        )
                        for tr in transcribe_rows:
                            v_link = tr.get("video_link") or ""
                            if v_link and (v_link.startswith("http://") or v_link.startswith("https://") or v_link.endswith(".mp4")):
                                if v_link not in seen_urls:
                                    seen_urls.add(v_link)
                                    direct_videos.append({
                                        "title": tr.get("video_title") or "Course video",
                                        "url": v_link,
                                        "videourl": v_link,
                                        "video_id": str(tr.get("video_id") or ""),
                                        "thumbnail": tr.get("video_thumbnail") or "",
                                    })
                    except Exception as tr_err:
                        logger.debug(f"Direct transcribe video search skipped/failed: {tr_err}")

                # 2. Tier 2: Sibling topic chunks from course_content if more videos are needed
                sibling_chunks = []
                needed = max_videos - len(direct_videos)
                if needed > 0 and (search_patterns or topic_codes):
                    if is_ship_type_q:
                        rows = await conn.fetch(
                            """
                            SELECT content_id, topic_name, topic_code, topic_video
                            FROM course_content
                            WHERE (
                                (cardinality($1::text[]) > 0 AND topic_name ILIKE ANY($1::text[]))
                                OR (cardinality($2::text[]) > 0 AND topic_code = ANY($2::text[]))
                            )
                            AND topic_video IS NOT NULL
                            AND jsonb_array_length(topic_video) > 0
                            ORDER BY 
                                CASE 
                                    WHEN topic_name ILIKE 'Types of Merchant Ships%' THEN 0
                                    WHEN topic_name ILIKE 'Ship Types%' OR topic_name ILIKE '1. Ship Types%' THEN 1
                                    WHEN topic_name ILIKE 'Container Ships%' THEN 2
                                    WHEN topic_name ILIKE 'General Cargo ships%' THEN 3
                                    WHEN cardinality($1::text[]) > 0 AND topic_name ILIKE ANY($1::text[]) THEN 4
                                    ELSE 5
                                END,
                                content_id ASC
                            LIMIT 15
                            """,
                            search_patterns,
                            topic_codes[:5]
                        )
                    else:
                        rows = await conn.fetch(
                            """
                            SELECT content_id, topic_name, topic_code, topic_video
                            FROM course_content
                            WHERE (
                                (cardinality($1::text[]) > 0 AND topic_name ILIKE ANY($1::text[]))
                                OR (cardinality($2::text[]) > 0 AND topic_code = ANY($2::text[]))
                            )
                            AND topic_video IS NOT NULL
                            AND jsonb_array_length(topic_video) > 0
                            ORDER BY 
                                CASE WHEN cardinality($1::text[]) > 0 AND topic_name ILIKE ANY($1::text[]) THEN 0 ELSE 1 END,
                                content_id ASC
                            LIMIT 15
                            """,
                            search_patterns,
                            topic_codes[:5]
                        )
                    for r in rows:
                        c_dict = dict(r)
                        sibling_chunks.append({
                            "topic_name": c_dict.get("topic_name"),
                            "topic_code": c_dict.get("topic_code"),
                            "videos": self._coerce_media(c_dict.get("topic_video")),
                        })

            if db_timings is not None:
                db_timings["db_query"] = db_timings.get("db_query", 0.0) + (time.perf_counter() - t_db0)

            # Rank sibling chunks for secondary videos
            more_videos = []
            if sibling_chunks and needed > 0:
                more_videos = self._filter_and_rank_videos(
                    sibling_chunks, [], query=query, max_videos=needed, context_chunks=chunks
                )

            # Combine direct videos (priority) with secondary sibling videos
            final_list = list(direct_videos)
            for mv in more_videos:
                u = mv.get("url") or mv.get("videourl")
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    final_list.append(mv)
                    if len(final_list) >= max_videos:
                        break

            return final_list

        except Exception as e:
            logger.debug(f"Failed to find sibling videos: {e}")
            return []

    def _filter_and_rank_pdfs(
        self,
        candidates: List[Tuple[Dict[str, Any], str]],
        query: str = "",
        max_pdfs: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Strictly filter and rank candidate PDFs based on relevance to the user's question,
        acronyms (e.g. EGCS, SOLAS, MARPOL, ECDIS, BWMS), topic alignment, and keyword matching.
        Ensures that only PDFs with names/topics genuinely related to the question are selected.
        """
        if not candidates:
            return []

        from services.maritime_acronyms import (
            find_acronyms_in_query,
            get_acronym_expansion,
            has_conflicting_acronym,
            GENERIC_MARITIME_WORDS,
            COMMON_ENGLISH_STOPWORDS,
        )

        query_acronyms = find_acronyms_in_query(query)
        stop_words = COMMON_ENGLISH_STOPWORDS | GENERIC_MARITIME_WORDS | {
            "document", "documents", "pdf", "pdfs", "file", "files", "course", "content", "related"
        }

        effective_query_words = [
            w.lower()
            for w in re.findall(r'\b[a-zA-Z]{3,}\b', query)
            if w.lower() not in stop_words
        ]
        query_content_words = [
            w.lower()
            for w in re.findall(r'\b[a-zA-Z]{3,}\b', query)
            if w.lower() not in COMMON_ENGLISH_STOPWORDS
        ]
        QUALIFIERS_PATTERN = r'\b(onboard\s+merchant\s+ships?|on\s+board\s+merchant\s+ships?|on\s+merchant\s+ships?|for\s+merchant\s+ships?|in\s+merchant\s+ships?|onboard\s+ships?|on\s+board\s+ships?|on\s+ships?|for\s+ships?|at\s+sea|for\s+seafarers)\b'

        # Blacklist of generic/placeholder titles that provide zero domain meaning
        GENERIC_TITLES = {
            "reference document", "document", "course document", "untitled",
            "exam guide", "introduction", "overview", "references", "table of contents",
            "contents", "none", "null", "image", "figure", "pdf", "index", "exam", "test"
        }

        scored_candidates = []
        seen_links = set()
        seen_titles = set()

        for item in candidates:
            if not isinstance(item, (tuple, list)) or len(item) < 2:
                continue
            pdf_dict, topic_name = item[0], item[1]
            if not isinstance(pdf_dict, dict):
                continue

            raw_link = (
                pdf_dict.get("Link") or pdf_dict.get("link")
                or pdf_dict.get("Url") or pdf_dict.get("url")
                or ""
            ).strip()
            clean_link = raw_link.lower().split("?")[0].rstrip("/")
            if not clean_link or clean_link in seen_links:
                continue

            title = (
                pdf_dict.get("Title") or pdf_dict.get("title")
                or pdf_dict.get("name") or ""
            ).strip()
            about = (pdf_dict.get("About") or pdf_dict.get("about") or "").strip()
            topic = (topic_name or "").strip()

            # If title is empty in candidate, check cached title or filename in link
            if not title:
                cached = pdf_service.get_title(raw_link)
                if cached:
                    title = cached
                else:
                    try:
                        fname = raw_link.split("/")[-1].split("?")[0].replace(".pdf", "")
                        if fname and not re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}', fname) and not re.match(r'^[0-9a-fA-F]{20,}', fname):
                            title = fname.replace("_", " ").replace("-", " ").strip()
                    except Exception:
                        pass

            # 1. Discard conflicting maritime acronyms
            if has_conflicting_acronym(query, f"{title} {about} {topic}"):
                continue

            # 2. Discard generic/placeholder titles
            if not title or title.lower() in GENERIC_TITLES or len(title) < 3:
                # If topic is highly specific and not generic, can adopt topic
                if topic and topic.lower() not in GENERIC_TITLES and len(topic) > 4:
                    title = topic
                else:
                    continue

            title_lower = title.lower()
            topic_lower = topic.lower()
            about_lower = about.lower()

            score = 0.0
            has_acr_title = False
            has_acr_topic = False
            has_acr_about = False

            # 3. Strict maritime acronym matching
            if query_acronyms:
                for acr in query_acronyms:
                    acr_lower = acr.lower()
                    if re.search(rf'\b{re.escape(acr_lower)}\b', title_lower):
                        has_acr_title = True
                        score += 250.0
                    elif re.search(rf'\b{re.escape(acr_lower)}\b', topic_lower):
                        has_acr_topic = True
                        score += 120.0
                    elif re.search(rf'\b{re.escape(acr_lower)}\b', about_lower):
                        has_acr_about = True
                        score += 20.0

                    for exp in get_acronym_expansion(acr):
                        exp_lower = exp.lower()
                        if exp_lower in title_lower:
                            has_acr_title = True
                            score += 220.0
                        elif exp_lower in topic_lower:
                            has_acr_topic = True
                            score += 100.0
                        elif exp_lower in about_lower:
                            has_acr_about = True
                            score += 15.0

                # CRITICAL RULE: If query asks about a specific acronym (e.g., EGCS),
                # the PDF MUST match the acronym or expansion in either its Title or Topic Name!
                # Merely mentioning it in an 'About' description or having an unrelated title like "Chemicals" is rejected.
                if not has_acr_title and not has_acr_topic:
                    continue

            # 4. Check effective query words
            match_words_in_title = 0
            match_words_in_topic = 0
            match_words_in_about = 0

            for qw in effective_query_words:
                qw_stem = re.sub(r'(ing|tion|tions|ed|es|s)$', '', qw)
                stem = qw_stem if len(qw_stem) >= 3 else qw
                if qw in title_lower or stem in title_lower:
                    match_words_in_title += 1
                    score += 35.0
                elif qw in topic_lower or stem in topic_lower:
                    match_words_in_topic += 1
                    score += 20.0
                elif qw in about_lower or stem in about_lower:
                    match_words_in_about += 1
                    score += 5.0

            # For non-acronym queries, strip boilerplate situational qualifiers from candidate title to reveal actual subject
            if not query_acronyms:
                title_subject = re.sub(QUALIFIERS_PATTERN, '', title_lower, flags=re.IGNORECASE).strip()
                title_subject = re.sub(r'^(guidelines?\s+for|guide\s+to|code\s+of|manual\s+for|rules\s+for|handbook\s+on)\s+', '', title_subject).strip()

                subject_match = any(qw in title_subject for qw in query_content_words)
                topic_match = any(qw in topic_lower for qw in query_content_words)

                if not subject_match and not topic_match:
                    continue

                if effective_query_words and match_words_in_title == 0 and match_words_in_topic == 0:
                    continue

            # 5. Reject single-word generic titles that are ambiguous (e.g. "Chemicals", "Difficulties", "Issues")
            # unless the user explicitly queried that specific term
            if len(title.split()) == 1 and title_lower in ("chemicals", "difficulties", "necessary", "operation", "issues"):
                if not any(title_lower == qw for qw in effective_query_words):
                    continue

            norm_title = re.sub(r'[^a-zA-Z0-9]', '', title_lower)
            if norm_title in seen_titles:
                continue

            # 6. Contextualize display title if title is generic but topic provides authentic domain clarity
            display_title = title
            if (
                topic
                and len(topic) > 3
                and topic_lower not in title_lower
                and any(w in topic_lower for w in (query_acronyms + [exp.lower() for acr in query_acronyms for exp in get_acronym_expansion(acr)]))
            ):
                if not has_acr_title and len(title) <= 45:
                    display_title = f"{topic} - {title}"

            seen_links.add(clean_link)
            seen_titles.add(norm_title)

            candidate_pdf = {
                **pdf_dict,
                "title": display_title,
                "Title": display_title,
                "topic_name": topic,
                "link": raw_link,
            }
            scored_candidates.append((score, candidate_pdf))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_candidates[:max_pdfs]]

    async def _find_sibling_pdfs(
        self,
        chunks: List[Dict[str, Any]],
        query: str = "",
        max_pdfs: int = 3,
        db_timings: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Look up related course_content rows in DB for this topic that have PDFs when retrieved chunks lack PDFs."""
        if not chunks and not query:
            return []

        try:
            primary_chunk = chunks[0] if chunks else {}
            search_patterns = self._build_sibling_search_patterns(query, primary_chunk)
            topic_codes = [c.get("topic_code") for c in (chunks or []) if c.get("topic_code")]

            if not search_patterns and not topic_codes:
                return []

            t_db0 = time.perf_counter()
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT content_id, topic_name, topic_code, topic_pdf
                    FROM course_content
                    WHERE (
                        (cardinality($1::text[]) > 0 AND topic_name ILIKE ANY($1::text[]))
                        OR (cardinality($2::text[]) > 0 AND topic_code = ANY($2::text[]))
                    )
                    AND topic_pdf IS NOT NULL
                    AND jsonb_array_length(topic_pdf) > 0
                    LIMIT 20
                    """,
                    search_patterns,
                    topic_codes[:5]
                )
            if db_timings is not None:
                db_timings["db_query"] = db_timings.get("db_query", 0.0) + (time.perf_counter() - t_db0)

            if not rows:
                return []

            candidate_raw_pdfs = []
            for r in rows:
                c_dict = dict(r)
                t_name = c_dict.get("topic_name") or ""
                raw_pdfs = self._coerce_media(c_dict.get("topic_pdf"))
                for pdf in raw_pdfs:
                    if isinstance(pdf, dict):
                        candidate_raw_pdfs.append((pdf, t_name))

            if not candidate_raw_pdfs:
                return []

            ranked_candidates = self._filter_and_rank_pdfs(
                candidate_raw_pdfs, query=query, max_pdfs=max_pdfs
            )

            if not ranked_candidates:
                return []

            resolve_tasks = [
                pdf_service.resolve_pdf_async(pdf_dict, chunk_topic_name=pdf_dict.get("topic_name", ""))
                for pdf_dict in ranked_candidates
            ]
            resolved = await asyncio.gather(*resolve_tasks, return_exceptions=True)

            candidate_pdfs = []
            for enriched in resolved:
                if isinstance(enriched, dict) and enriched.get("link") and (enriched.get("title") or "").strip():
                    candidate_pdfs.append(enriched)

            return pdf_service.deduplicate_titles(candidate_pdfs)[:max_pdfs]

        except Exception as e:
            logger.debug(f"Failed to find sibling PDFs: {e}")
            return []

    async def _run_media_enrichment_task(
        self,
        retrieval_chunks: List[Dict[str, Any]],
        current_query: str,
        video_suggestions: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, float], float]:
        """Run image, PDF, and video enrichment concurrently in background while LLM generates answer."""
        if not retrieval_chunks:
            return [], [], [], {
                "image_filter_cache": 0.0,
                "sibling_images": 0.0,
                "pdf_resolution": 0.0,
                "sibling_pdfs": 0.0,
                "sibling_videos": 0.0,
                "db_query": 0.0,
            }, 0.0

        t_media = time.perf_counter()
        media_sub_timings: Dict[str, float] = {
            "image_filter_cache": 0.0,
            "sibling_images": 0.0,
            "pdf_resolution": 0.0,
            "sibling_pdfs": 0.0,
            "sibling_videos": 0.0,
            "db_query": 0.0,
        }

        async def _enrich_images() -> List[Dict[str, Any]]:
            t_if0 = time.perf_counter()
            images = await self._filter_and_rank_images(retrieval_chunks, query=current_query, max_images=5)
            media_sub_timings["image_filter_cache"] = time.perf_counter() - t_if0

            if len(images) < 3 and retrieval_chunks:
                t_sib0 = time.perf_counter()
                needed = 3 - len(images)
                sibling_images = await self._find_sibling_images(
                    retrieval_chunks, query=current_query, max_images=needed, db_timings=media_sub_timings
                )
                seen_img_keys = {img.get("Url") or img.get("url") for img in images}
                seen_titles = {re.sub(r'[^a-zA-Z0-9]', '', (img.get("Title") or img.get("title") or "")).lower() for img in images}
                for simg in sibling_images:
                    s_key = simg.get("Url") or simg.get("url")
                    s_title = re.sub(r'[^a-zA-Z0-9]', '', (simg.get("Title") or simg.get("title") or "")).lower()
                    if s_key and s_key not in seen_img_keys and (not s_title or s_title not in seen_titles):
                        seen_img_keys.add(s_key)
                        if s_title:
                            seen_titles.add(s_title)
                        images.append(simg)
                        if len(images) >= 3:
                            break
                media_sub_timings["sibling_images"] = time.perf_counter() - t_sib0
            return images

        async def _enrich_pdfs() -> List[Dict[str, Any]]:
            t_pr0 = time.perf_counter()
            pdfs: List[Dict[str, Any]] = []

            # 1. Collect all candidate PDFs from retrieval chunks
            raw_chunk_candidates: List[Tuple[Dict[str, Any], str]] = []
            for chunk in retrieval_chunks:
                chunk_topic_name = chunk.get("topic_name") or chunk.get("title") or ""
                for pdf in (chunk.get("pdfs", []) or chunk.get("topic_pdf", [])):
                    if isinstance(pdf, dict):
                        raw_chunk_candidates.append((pdf, chunk_topic_name))

            # 2. Strictly filter and rank chunk PDFs against current_query
            filtered_chunk_candidates = self._filter_and_rank_pdfs(
                raw_chunk_candidates, query=current_query, max_pdfs=3
            )

            # 3. Asynchronously resolve authentic document titles for top candidates
            if filtered_chunk_candidates:
                tasks = [
                    pdf_service.resolve_pdf_async(p, chunk_topic_name=p.get("topic_name", ""))
                    for p in filtered_chunk_candidates
                ]
                resolved_pdfs = await asyncio.gather(*tasks, return_exceptions=True)
                for enriched_pdf in resolved_pdfs:
                    if isinstance(enriched_pdf, dict) and enriched_pdf.get("link") and (enriched_pdf.get("title") or "").strip():
                        pdfs.append(enriched_pdf)

            pdfs = pdf_service.deduplicate_titles(pdfs)
            media_sub_timings["pdf_resolution"] = time.perf_counter() - t_pr0

            # 4. Sibling PDF lookup if fewer than 3 relevant PDFs exist in retrieved chunks
            if len(pdfs) < 3 and retrieval_chunks:
                t_sib0 = time.perf_counter()
                needed = 3 - len(pdfs)
                sibling_pdfs = await self._find_sibling_pdfs(
                    retrieval_chunks, query=current_query, max_pdfs=needed, db_timings=media_sub_timings
                )
                seen_pdf_keys = {p.get("link", "").lower().split("?")[0].rstrip("/") for p in pdfs if p.get("link")}
                seen_pdf_titles = {re.sub(r'[^a-zA-Z0-9]', '', (p.get("title") or "")).lower() for p in pdfs if p.get("title")}

                for spdf in sibling_pdfs:
                    p_link = spdf.get("link", "").lower().split("?")[0].rstrip("/")
                    s_title = re.sub(r'[^a-zA-Z0-9]', '', (spdf.get("title") or "")).lower()

                    if p_link and p_link in seen_pdf_keys:
                        continue
                    if s_title and s_title in seen_pdf_titles:
                        continue

                    seen_pdf_keys.add(p_link)
                    if s_title:
                        seen_pdf_titles.add(s_title)
                    pdfs.append(spdf)
                    if len(pdfs) >= 3:
                        break
                media_sub_timings["sibling_pdfs"] = time.perf_counter() - t_sib0

            return pdf_service.deduplicate_titles(pdfs)[:3]

        async def _enrich_videos() -> List[Dict[str, Any]]:
            videos = self._filter_and_rank_videos(
                retrieval_chunks, video_suggestions, query=current_query, max_videos=5
            )
            if len(videos) < 5 and retrieval_chunks:
                t_sib0 = time.perf_counter()
                needed = 5 - len(videos)
                sibling_videos = await self._find_sibling_videos(
                    retrieval_chunks, query=current_query, max_videos=needed, db_timings=media_sub_timings
                )
                combined = list(videos)
                seen_vid_keys = {v.get("url") or v.get("videourl") for v in videos}
                for svid in sibling_videos:
                    v_key = svid.get("url") or svid.get("videourl")
                    if v_key and v_key not in seen_vid_keys:
                        seen_vid_keys.add(v_key)
                        combined.append(svid)
                videos = self._filter_and_rank_videos(
                    retrieval_chunks, combined, query=current_query, max_videos=5
                )
                media_sub_timings["sibling_videos"] = time.perf_counter() - t_sib0
            return videos

        all_images, all_pdfs, final_videos = await asyncio.gather(
            _enrich_images(),
            _enrich_pdfs(),
            _enrich_videos(),
        )

        total_media_time = time.perf_counter() - t_media

        return all_images, all_pdfs, final_videos, media_sub_timings, total_media_time

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
            company_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """Embed the query, search FAISS, and return normalized chunks + videos."""

        if not query.strip():
            return [], []

        try:
            # Acronym domain expansion for vector embedding & BM25 search
            effective_search_query = query
            try:
                acrs = find_acronyms_in_query(query)
                for acr in acrs:
                    exps = get_acronym_expansion(acr)
                    if exps:
                        effective_search_query += " " + " ".join(exps[:3])
            except Exception:
                pass

            raw_chunks = await self.vector_store.search_with_embeddings(effective_search_query, k=k)

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

                # Zero-hallucination relevance filter:
                score = merged.get("_score")
                has_bm25 = merged.get("_bm25_score") is not None and merged.get("_bm25_score", 0) > 0
                has_topic_match = merged.get("_has_topic_match", False)

                if score is not None:
                    try:
                        # If no exact keyword matched and distance is very high (>1.45), drop noise
                        if not has_bm25 and not has_topic_match and float(score) > 1.45:
                            logger.info(
                                f"Dropping low-relevance chunk: topic='{merged.get('topic_name')}', score={score}"
                            )
                            continue
                    except (TypeError, ValueError):
                        pass

                logger.debug(
                    "MERGED CHUNK = {}",
                    merged
                )
                retrieval_chunks.append(self._normalize_chunk(merged))

            # Safety fallback: If filter dropped all chunks but raw_chunks exist, keep the top 2 ONLY for marine queries/acronyms
            if not retrieval_chunks and raw_chunks:
                from services.off_topic_detector import is_marine_domain_query, is_obvious_marine_query
                from services.maritime_acronyms import find_acronyms_in_query
                if is_marine_domain_query(query) or is_obvious_marine_query(query) or bool(find_acronyms_in_query(query)):
                    logger.info("⚠️ Filter dropped all chunks; retaining top raw chunks as safety fallback for marine query")
                    for chunk in raw_chunks[:2]:
                        cid = chunk.get("content_id") or chunk.get("id")
                        merged = dict(chunk)
                        if cid is not None and int(cid) in fetched_rows:
                            merged = {**merged, **fetched_rows[int(cid)], "content_id": int(cid)}
                        retrieval_chunks.append(self._normalize_chunk(merged))
                else:
                    logger.info(f"🚫 Dropped low-relevance chunks for non-marine query '{query[:50]}'")

            # 🌟 IMMEDIATE APPROVED FEEDBACK MEMORY CHECK
            try:
                from api.dependencies import get_approved_memory_service
                approved_service = await get_approved_memory_service()
                approved_mem = await approved_service.search_approved_memory(
                    query,
                    company_id=company_id,
                )
                if approved_mem and approved_mem.get("preferred_response"):
                    sme_pref = approved_mem["preferred_response"]
                    logger.info(f"🌟 Retrieved SME-Approved Override in _retrieve_chunks for query '{query[:50]}'")
                    sme_chunk = {
                        "content_id": 999999,
                        "topic_code": "SME-OFFICIAL-GUIDANCE",
                        "topic_name": "SME Approved Guidance",
                        "topic_content": sme_pref,
                        "content": f"SME Approved Guidance\n\n[OFFICIAL SME-VERIFIED GUIDANCE - HIGH PRIORITY OVERRIDE]:\n{sme_pref}",
                        "videos": [],
                        "images": [],
                        "pdfs": [],
                        "_score": 1.0,
                        "_rank": 0,
                        "_is_sme_approved": True,
                        "_sme_preferred_response": sme_pref,
                        "_sme_feedback_id": approved_mem.get("feedback_id"),
                    }
                    retrieval_chunks.insert(0, sme_chunk)
            except Exception as mem_err:
                logger.warning(f"Approved memory search error in _retrieve_chunks: {mem_err}")

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

        # Fast return if transcribe store has no index or 0 vectors
        if hasattr(self.transcribe_vector_store.store, "index") and (self.transcribe_vector_store.store.index is None or getattr(self.transcribe_vector_store.store.index, "ntotal", 0) == 0):
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
        if not previous_questions or not current_query:
            return current_query

        # Check if current query is already standalone (no coreference pronouns or references)
        q_lower = current_query.lower().strip()
        has_reference = bool(re.search(
            r'\b(it|this|that|these|those|above|its|them|he|she|they|point\s*\d+|step\s*\d+|second\s*one|first\s*one|former|latter|same|again|previous|earlier)\b',
            q_lower
        ))
        
        # Only treat as a conversational follow-up if it starts with a follow-up phrase or has coreferences
        is_followup_starter = q_lower.startswith((
            "and ", "what about", "how about", "why ", "why?", "how come", "also ",
            "tell more", "explain more", "more details", "what else", "what next", "continue"
        ))

        # Standalone topic queries (e.g. "enclosed space entry", "fire fighting", "SEEMP") are not follow-ups
        if not has_reference and not is_followup_starter:
            return current_query

        try:
            last_question = previous_questions[-1]

            prompt = f"""You are a query rewriting assistant.

Previous user question:
{last_question}

Last assistant answer:
{last_answer or "N/A"}

Current question:
{current_query}

Task:
1. If the current question depends on the previous question → rewrite it as a standalone question.
2. If the current question refers to "point 1", "point 2", "this", "that", "above" → resolve it using the assistant's last answer.
3. If the question is independent → return it unchanged.

Rules:
- Output ONLY the final standalone question.
"""

            response = await self.openai_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                model="gpt-4o-mini",
                max_tokens=60,
            )

            rewritten = response.strip()
            return rewritten or current_query

        except Exception as e:
            logger.exception(f"❌ Query rewrite failed: {e}")
            return current_query
        
    async def generate_understanding(
        self,
        query: str
    ) -> str:
        """
        Generate user-friendly understanding summary (Fast return - not used in final answer).
        """
        return ""    

    async def run_chat(
        self,
        user_id: str,
        session_id: str,
        db_messages: list,
        current_query: str,
        category: str | None = None,
        user_details: dict | None = None,
        status_callback: Optional[Any] = None,
        stream_callback: Optional[Any] = None,
    ) -> Tuple[NodeResponse, List[Dict[str, Any]], str, str, Dict[str, Any]]:

        logger.info("Running chat pipeline")
        t_pipeline_start = time.perf_counter()
        latencies: Dict[str, float] = {}

        if status_callback:
            try:
                await status_callback("thinking", "Dolphin is thinking...")
            except Exception as e:
                logger.warning(f"Status callback failed: {e}")

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
        #  FAST-PATH GREETING & SOCIAL INTENT DETECTION
        # -----------------------------
        simple_social = is_simple_social_intent(current_query)
        is_user_greeting = is_greeting_query(current_query)

        # -----------------------------
        # DYNAMIC JIT ACRONYM RESOLUTION (Only if not simple social greeting/goodbye)
        # -----------------------------
        if not simple_social:
            words_raw = current_query.strip().split()
            if 1 <= len(words_raw) <= 3:
                for w in words_raw:
                    w_token = re.sub(r'[^a-zA-Z0-9]', '', w).upper()
                    if 2 <= len(w_token) <= 8:
                        from services.maritime_acronyms import is_known_maritime_acronym, AMBIGUOUS_SHORT_WORDS
                        if (
                            not is_known_maritime_acronym(w_token)
                            and not is_marine_domain_query(w_token)
                            and w_token not in AMBIGUOUS_SHORT_WORDS
                        ):
                            try:
                                from services.dynamic_acronym_service import dynamic_acronym_service
                                await dynamic_acronym_service.resolve_acronym(w_token)
                            except Exception as e:
                                logger.debug(f"Dynamic acronym check error for '{w_token}': {e}")

        # -----------------------------
        #  FAST-PATH DIRECT MARITIME QUERIES (Step 3)
        # -----------------------------
        q_lower = current_query.lower().strip()
        words = q_lower.split()

        is_quiz_or_summary = bool(re.search(
            r'\b(quiz|quizz|mcq|test me|practice test|mock test|summary|summarize|overview|recap)\b',
            q_lower
        ))
        has_coreference = bool(re.search(
            r'\b(it|this|that|these|those|above|its|them|he|she|they|him|her|point\s*\d+|step\s*\d+|second\s*one|first\s*one|former|latter|same|again|previous|earlier)\b',
            q_lower
        ))
        is_followup_starter = q_lower.startswith((
            "and ", "what about", "how about", "why ", "why?", "how come", "also ",
            "tell more", "explain more", "more details", "what else", "what next", "continue"
        ))

        # Check if query is a verified marine technical term, acronym, machinery phrase, or domain query
        is_tech_term = (
            bool(find_acronyms_in_query(current_query))
            or is_marine_domain_query(current_query)
            or any(w in q_lower for w in ("pump", "pumps", "valve", "valves", "bbs", "bog", "bob", "hazard", "hazards", "alarm", "alarms"))
        )
        if not is_tech_term:
            try:
                from services.dynamic_acronym_service import dynamic_acronym_service
                is_tech_term = any(dynamic_acronym_service.is_known_acronym(w) for w in words if 2 <= len(w) <= 10)
            except Exception:
                pass

        is_direct_marine = (
            not simple_social
            and not is_quiz_or_summary
            and not has_coreference
            and not is_followup_starter
            and not is_off_topic_query(current_query)
            and (
                is_obvious_marine_query(current_query)
                or is_marine_domain_query(current_query)
                or is_tech_term
            )
        )

        if simple_social:
            social_intent_map = {
                "GREETING": ("greeting", "GREETING"),
                "GOODBYE": ("goodbye", "GOODBYE"),
                "THANK": ("thank", "THANK"),
                "WELL_WISH": ("well_wish", "WELL_WISH"),
            }
            node_type, user_category = social_intent_map.get(simple_social, ("greeting", "GREETING"))
            standalone_query = current_query
            detected_name = extract_name(current_query)
            router_decision = {
                "node_type": node_type,
                "short_topic": node_type,
                "reason": f"Instant social routing: {current_query}",
                "user_name": detected_name,
                "category": user_category,
                "standalone_query": current_query,
            }
            latencies["query_rewrite"] = 0.0
            latencies["router_classify"] = 0.0
            logger.info(f"⚡ [Fast-Path] Instant Social Routing: '{current_query}' → {node_type} (0.00s)")
        elif is_direct_marine:
            standalone_query = current_query
            node_type = "query"
            user_category = self._normalize_category(category, "QUERY")
            router_decision = {
                "node_type": "query",
                "short_topic": "marine",
                "reason": f"Direct standalone marine query fast-path: {current_query}",
                "user_name": None,
                "category": user_category,
                "standalone_query": current_query,
            }
            latencies["query_rewrite"] = 0.0
            latencies["router_classify"] = 0.0
            logger.info(f"⚡ [Fast-Path] Direct Standalone Marine Query: '{current_query}' → query (0.00s)")
        else:
            # -----------------------------
            #  QUERY REWRITE (NEW)
            # -----------------------------
            last_answer = None
            for msg in reversed(cleaned_messages):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    last_answer = msg.get("content")
                    break

            t_rw_cls = time.perf_counter()
            rewrite_task = asyncio.create_task(
                self.rewrite_query(
                    current_query=current_query,
                    previous_questions=previous_questions,
                    last_answer=last_answer,
                )
            )
            classify_task = asyncio.create_task(
                self.analyzer.classify_for_router(
                    current_query,
                    previous_questions,
                )
            )
            standalone_query, router_decision = await asyncio.gather(rewrite_task, classify_task)
            rw_cls_dur = time.perf_counter() - t_rw_cls
            latencies["query_rewrite"] = rw_cls_dur
            latencies["router_classify"] = rw_cls_dur
            logger.info(f"⏱️ [Timer] Concurrent Rewrite & Classify (LLM): {rw_cls_dur:.2f}s")

            node_type = router_decision.get("node_type", "").lower()
            user_category = self._normalize_category(
                category or router_decision.get("category"),
                "QUERY",
            )

            # Guard: If router mistakenly classified a technical term / machinery query as social or off-topic, override to query
            if is_tech_term and not simple_social and not is_off_topic_query(current_query):
                if node_type in ("goodbye", "greeting", "fallback", "negative", "off_topic") or router_decision.get("category") == "OFF_TOPIC":
                    logger.info(f"⚡ Overriding false router node_type '{node_type}' to 'query' for technical term: '{current_query}'")
                    node_type = "query"
                    user_category = "QUERY"
                    router_decision["node_type"] = "query"
                    router_decision["category"] = "QUERY"

        understanding_summary = ""

        logger.info(f"🧠 Rewritten Query: {standalone_query} | Route: {node_type}")

        is_social = node_type in {"greeting", "goodbye", "thank", "well_wish"}

        # -----------------------------
        # ⚡ FAST MODE
        # -----------------------------
        if is_social:
            logger.info(f"⚡ FAST MODE: {node_type}")

            user_category = user_category or "GREETING"
            messages_with_user = await self.append_message(
                session_id,
                "user",
                current_query,
                user_category,
                user_id=user_id,
                existing_messages=cleaned_messages,
            )
            full_history = self._clean_messages(messages_with_user)
            history_for_llm = []
            meaningful_history = []
            retrieval_chunks = []
            video_suggestions = []
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

            if status_callback:
                try:
                    await status_callback("fetching", "Dolphin is fetching relevant information...")
                except Exception as e:
                    logger.warning(f"Status callback failed: {e}")

            if is_off_topic_query(current_query) or is_off_topic_query(standalone_query):
                logger.info("OFF TOPIC QUESTION DETECTED BEFORE RETRIEVAL")
                retrieval_chunks = []
                video_suggestions = []
                sme_checked = False
            else:
                t_init_ret = time.perf_counter()
                user_comp_id = (user_details or {}).get("company_id")
                retrieval_chunks, video_suggestions = await self._retrieve_chunks(
                    standalone_query or current_query,
                    company_id=str(user_comp_id) if user_comp_id is not None else None,
                )
                latencies["initial_chunk_retrieval"] = time.perf_counter() - t_init_ret
                logger.info(f"⏱️ [Timer] Initial Chunk Retrieval: {latencies['initial_chunk_retrieval']:.2f}s")
                sme_checked = True

        else:
            retrieval_chunks = []
            video_suggestions = []
            sme_checked = False
            
        video_suggestions = self._normalize_video_suggestions(
            video_suggestions
        )

        # -----------------------------
        # 🚀 BACKGROUND MEDIA ENRICHMENT (Concurrent with LLM generation)
        # -----------------------------
        media_enrichment_task: Optional[asyncio.Task] = None
        if retrieval_chunks and not is_social and node_type in {"query", "summary", "quiz"}:
            logger.info("🚀 Launching background media enrichment task concurrent with LLM")
            media_enrichment_task = asyncio.create_task(
                self._run_media_enrichment_task(
                    retrieval_chunks,
                    current_query,
                    video_suggestions,
                )
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
            "_sme_checked": sme_checked,
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
            "status_callback": status_callback,
            "stream_callback": stream_callback,
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

                if (
                    is_off_topic_query(current_query)
                    or is_off_topic_query(standalone_query)
                    or (
                        (user_category == "OFF_TOPIC" or router_decision.get("category") == "OFF_TOPIC")
                        and not is_tech_term
                        and not is_marine_domain_query(current_query)
                        and not is_marine_domain_query(standalone_query)
                    )
                ):

                    logger.info("🚫 OFF TOPIC QUESTION DETECTED")

                    from services.off_topic_detector import generate_dynamic_off_topic_response
                    out_of_scope_text, dynamic_suggestions = await generate_dynamic_off_topic_response(
                        current_query or standalone_query
                    )

                    if stream_callback:
                        try:
                            tokens = re.findall(r'\S+\s*|\n+', out_of_scope_text)
                            for tok in tokens:
                                await stream_callback({"type": "content", "token": tok})
                            state["_streamed_live"] = True
                        except Exception as stream_err:
                            logger.warning(f"Failed streaming off-topic response: {stream_err}")

                    state["node_response"] = {
                        "type": "query",
                        "content": out_of_scope_text,
                        "sections": [
                            {
                                "topic_code": "",
                                "topic_name": "",
                                "content": out_of_scope_text,
                            }
                        ],
                        "chunks_used": [],
                        "videos": [],
                        "images": [],
                        "pdfs": [],
                        "question_suggestions": dynamic_suggestions,
                        "metadata": {
                            "routing_reason": "off_topic",
                            "out_of_scope": True,
                        }
                    }
                    state["retrieval_chunks"] = []
                    state["video_suggestions"] = []
                    state["company_answer"] = None

                else:

                    # 🚀 STRATEGY 3: Parallelize Company & Course Retrieval
                    t_ret_start = time.perf_counter()
                    user_comp_id = (state.get("user_profile") or {}).get("company_id")
                    if user_comp_id:
                        logger.info("⚡ Concurrently executing Course and Company Retrieval nodes")
                        course_task = asyncio.create_task(
                            retrieval_node(state, self.vector_store, None)
                        )
                        company_task = asyncio.create_task(
                            company_retrieval_node(state, self.company_vector_store)
                        )
                        state_res, state_comp = await asyncio.gather(course_task, company_task)
                        state = state_res
                        state["company_chunks"] = state_comp.get("company_chunks", [])
                    else:
                        state = await retrieval_node(
                            state,
                            self.vector_store,
                            None
                        )
                        state["company_chunks"] = []

                    dur_ret = time.perf_counter() - t_ret_start
                    latencies["retrieval_node"] = dur_ret
                    latencies["company_retrieval"] = dur_ret if user_comp_id else 0.0
                    logger.info(f"⏱️ [Timer] Concurrent Course & Company Retrieval: {dur_ret:.2f}s")

                    if status_callback:
                        try:
                            await status_callback("generating", "Dolphin is generating response...")
                        except Exception as e:
                            logger.warning(f"Status callback failed: {e}")

                    # Parallelize query_node and company_query_node if company_chunks exist
                    t_gen = time.perf_counter()
                    if state.get("company_chunks"):
                        course_task = asyncio.create_task(
                            query_node(
                                state,
                                self.openai_service,
                                self.suggestion_service,
                                self.vector_store,
                            )
                        )
                        company_task = asyncio.create_task(
                            company_query_node(
                                state,
                                self.openai_service,
                            )
                        )
                        state_res, comp_res = await asyncio.gather(course_task, company_task)
                        state = state_res
                        state["company_answer"] = comp_res.get("company_answer")
                    else:
                        state = await query_node(
                            state,
                            self.openai_service,
                            self.suggestion_service,
                            self.vector_store,
                        )
                        state["company_answer"] = None
                    latencies["answer_generation"] = time.perf_counter() - t_gen
                    logger.info(f"⏱️ [Timer] Answer Generation (OpenAI LLM): {latencies['answer_generation']:.2f}s")

            elif node_type == "greeting":

                if status_callback:
                    try:
                        await status_callback("generating", "Dolphin is generating response...")
                    except Exception as e:
                        logger.warning(f"Status callback failed: {e}")

                state = await greeting_node(state)

            elif node_type == "goodbye":
                state = await goodbye_node(state)

            elif node_type == "thank":
                state = await thank_node(state)

            elif node_type == "well_wish":
                state = await well_wish_node(state)

            elif node_type == "threadning":
                state = await threadning_node(state)

            elif node_type == "negative":
                state = await negative_node(state)

            else:

                if status_callback:
                    try:
                        await status_callback("generating", "Dolphin is generating response...")
                    except Exception as e:
                        logger.warning(f"Status callback failed: {e}")

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

        # Collect retrieval chunks and media from resulting state / response
        retrieval_chunks = (
            state.get("retrieval_chunks", [])
            or state.get("chunks", [])
            or state.get("last_query_chunks", [])
            or raw_result.get("retrieval_chunks", [])
            or []
        )
        video_suggestions = (
            state.get("video_suggestions", [])
            or state.get("videos", [])
            or raw_result.get("video_suggestions", [])
            or []
        )
        if not video_suggestions and retrieval_chunks:
            video_suggestions = self._build_video_suggestions(retrieval_chunks)

        is_resp_out_of_scope = (
            (validated.metadata or {}).get("out_of_scope") is True
            or is_off_topic_query(current_query)
            or any(
                s.get("topic_name", "").strip().lower() in ("out of scope", "off topic", "unrelated")
                or "outside the marine training curriculum" in s.get("content", "").lower()
                or "outside the maritime curriculum" in s.get("content", "").lower()
                or "specialized exclusively in maritime" in s.get("content", "").lower()
                for s in (validated.sections or [])
            )
        )
        if is_resp_out_of_scope or is_social:
            if media_enrichment_task and not media_enrichment_task.done():
                media_enrichment_task.cancel()
            all_images = []
            all_pdfs = []
            final_videos = []
            all_topic_codes = []
            company_answer = None
        else:
            t_media_wait = time.perf_counter()
            if media_enrichment_task is not None:
                try:
                    all_images, all_pdfs, final_videos, media_sub_timings, total_media_time = await media_enrichment_task
                except Exception as e:
                    logger.exception(f"❌ Background media enrichment failed: {e}")
                    all_images, all_pdfs, final_videos, media_sub_timings, total_media_time = await self._run_media_enrichment_task(
                        retrieval_chunks, current_query, video_suggestions
                    )
            else:
                all_images, all_pdfs, final_videos, media_sub_timings, total_media_time = await self._run_media_enrichment_task(
                    retrieval_chunks, current_query, video_suggestions
                )

            all_topic_codes = []
            for chunk in retrieval_chunks:
                topic_code = chunk.get("topic_code")
                if topic_code and topic_code not in all_topic_codes:
                    all_topic_codes.append(topic_code)

            company_answer = state.get("company_answer")
            media_await_time = time.perf_counter() - t_media_wait
            latencies["media_enrichment"] = media_await_time
            latencies["media_image_filter_cache"] = media_sub_timings.get("image_filter_cache", 0.0)
            latencies["media_sibling_images"] = media_sub_timings.get("sibling_images", 0.0)
            latencies["media_pdf_resolution"] = media_sub_timings.get("pdf_resolution", 0.0)
            latencies["media_sibling_pdfs"] = media_sub_timings.get("sibling_pdfs", 0.0)
            latencies["media_sibling_videos"] = media_sub_timings.get("sibling_videos", 0.0)
            latencies["media_db_query"] = media_sub_timings.get("db_query", 0.0)

            logger.info(f"⏱️ [Timer] Media & Sibling Lookup: wait={media_await_time:.2f}s | background_total={total_media_time:.2f}s")
            logger.info(
                f"⏱️ [Timer Breakdown] Media Substeps: "
                f"image_filter_cache={latencies['media_image_filter_cache']:.3f}s | "
                f"sibling_images={latencies['media_sibling_images']:.3f}s | "
                f"pdf_resolution={latencies['media_pdf_resolution']:.3f}s | "
                f"sibling_pdfs={latencies['media_sibling_pdfs']:.3f}s | "
                f"sibling_videos={latencies['media_sibling_videos']:.3f}s | "
                f"db_query={latencies['media_db_query']:.3f}s"
            )

        # Synchronize validated model
        validated.images = all_images
        validated.pdfs = all_pdfs
        validated.videos = final_videos
        validated.video_suggestions = final_videos

        metadata_to_save = {
            **(validated.metadata or {}),
            "category": validated.metadata.get("category", "QUERY"),
            "images": all_images,
            "pdfs": all_pdfs,
            "videos": final_videos,
            "video_suggestions": final_videos,
            "topic_codes": all_topic_codes,
            "company_answer": company_answer,
            "question_suggestions": validated.question_suggestions or [],
        }

        updated_messages = await self.append_message(
            session_id,
            "assistant",
            assistant_content,
            validated.metadata.get("category", "QUERY"),
            metadata_to_save,
            user_id=user_id,
            existing_messages=messages_with_user,
        )

        logger.info("========== ASSISTANT SAVE DEBUG ==========")
        logger.info(f"validated.content = {repr(validated.content)}")
        logger.info("==========================================")

        final_cleaned_history = self._clean_messages(updated_messages)

        if final_cleaned_history and isinstance(final_cleaned_history[-1], dict) and final_cleaned_history[-1].get("role") == "assistant":
            final_cleaned_history[-1]["images"] = all_images
            final_cleaned_history[-1]["pdfs"] = all_pdfs
            final_cleaned_history[-1]["videos"] = final_videos
            final_cleaned_history[-1]["video_suggestions"] = final_videos

        latencies["pipeline_total"] = time.perf_counter() - t_pipeline_start
        return (
            validated,
            final_cleaned_history,
            standalone_query,
            understanding_summary,
            {
                "videos": [] if (is_resp_out_of_scope or is_social) else final_videos,
                "images": [] if (is_resp_out_of_scope or is_social) else all_images,
                "pdfs": [] if (is_resp_out_of_scope or is_social) else all_pdfs,
                "topic_codes": [] if (is_resp_out_of_scope or is_social) else all_topic_codes,
                "company_answer": None if (is_resp_out_of_scope or is_social) else company_answer,
                "latencies": latencies,
            }
        )



