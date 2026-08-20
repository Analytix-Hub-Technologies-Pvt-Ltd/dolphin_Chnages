from functools import lru_cache

from retrieval.faiss_store import FAISSStore
from services.chat_service import ChatService
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService
from services.session_service import SessionService


@lru_cache(maxsize=1)
def get_chat_service(
    openai_service: OpenAIService,
    embedder: EmbeddingService,
    store: FAISSStore,
    session_service: SessionService,
) -> ChatService:
    return ChatService(
        openai_service=openai_service,
        embedder=embedder,
        store=store,
        session_service=session_service,
    )