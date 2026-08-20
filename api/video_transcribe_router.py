from __future__ import annotations

from asyncpg import Pool
from fastapi import APIRouter, Depends

from api.dependencies import get_db_pool, get_transcribe_store
from models.transcribe_models import TranscribeRequest, VideoInfoRequest
from retrieval.faiss_store import FAISSStore
from retrieval.video_embedding import VideoTranscriptStore
from services.video_transcribe_service import VideoTranscribeService

router = APIRouter(prefix="/transcribe", tags=["transcribe"])

@router.post("/video")
async def video_trascribe_with_limit(request: TranscribeRequest, pool: Pool = Depends(get_db_pool), store: FAISSStore = Depends(get_transcribe_store)):
    return await VideoTranscribeService(pool, VideoTranscriptStore(store)).video_transcribe(request)
