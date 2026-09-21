from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from api.dependencies import (
    get_faiss_store,
    get_embedding_service,
    get_openai_service,
)
from core.redis_client import redis_service
from models.database import get_pool
from services.chat_service import ChatService
from services.session_service import SessionService
from services.stt_service import FasterWhisperService
from services.tts_normalizer import TTSNormalizer
from services.tts_service import PiperTTSService

router = APIRouter(prefix="/ws", tags=["voice"])


@router.websocket("/voice/{session_id}")
async def voice_websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Real-Time WebSocket Voice Assistant Endpoint.

    Flow:
    1. Client connects with session_id.
    2. Receives chunked audio streams from browser microphone with VAD.
    3. Faster-Whisper transcribes speech into text when utterance ends.
    4. Passes final transcript directly to EXISTING ChatService.run_chat().
    5. Sends full unaltered Dolphin response to UI for rich chat history.
    6. Normalizes response text for speech and generates streaming sentence-level Piper TTS audio.
    7. Supports instant interruption (barge-in) and cancellation.
    """
    await websocket.accept()
    logger.info(f"🎙️ [Voice WS] Connection established for session: {session_id}")

    pool = await get_pool()
    session_service = SessionService(pool)
    openai_service = get_openai_service()
    embedder = get_embedding_service()
    store = get_faiss_store()

    chat_service = ChatService(openai_service, embedder, store, session_service)
    stt_service = FasterWhisperService.get_instance()
    tts_service = PiperTTSService.get_instance()

    user_id = "test-user"
    user_details = {}
    audio_buffer = bytearray()
    current_tts_cancel_event: Optional[asyncio.Event] = None
    state = "IDLE"

    try:
        # Load active session details
        stored_user = await redis_service.get_active_session(session_id)
        if stored_user:
            user_id = stored_user

        user_details = await redis_service.get_user_details(user_id) or {}
        state = "LISTENING"

        await websocket.send_text(
            json.dumps({
                "type": "session_started",
                "session_id": session_id,
                "user_id": user_id,
                "state": state
            })
        )

        while True:
            # Receive either text control frame or binary audio frame
            message = await websocket.receive()

            if "text" in message:
                try:
                    payload = json.loads(message["text"])
                except Exception:
                    continue

                msg_type = payload.get("type", "")

                # 1. Voice Start / Init
                if msg_type == "voice_start":
                    if payload.get("user_id"):
                        user_id = payload["user_id"]
                        user_details = await redis_service.get_user_details(user_id) or {}
                    audio_buffer.clear()
                    state = "LISTENING"
                    await websocket.send_text(json.dumps({"type": "listening", "state": state}))

                # 2. Audio Chunk (Base64 JSON encoded)
                elif msg_type == "audio_chunk":
                    chunk_b64 = payload.get("data", "")
                    if chunk_b64:
                        chunk_bytes = base64.b64decode(chunk_b64)
                        audio_buffer.extend(chunk_bytes)
                        if state != "USER_SPEAKING":
                            state = "USER_SPEAKING"
                            await websocket.send_text(json.dumps({"type": "speech_started", "state": state}))

                # 3. Speech End / VAD Silence Detected -> Process Audio
                elif msg_type == "speech_end":
                    if len(audio_buffer) < 1000:
                        audio_buffer.clear()
                        state = "LISTENING"
                        await websocket.send_text(json.dumps({"type": "listening", "state": state}))
                        continue

                    state = "PROCESSING"
                    await websocket.send_text(json.dumps({"type": "processing_started", "state": state}))

                    captured_audio = bytes(audio_buffer)
                    audio_buffer.clear()

                    t_stt_start = time.perf_counter()
                    transcript = await stt_service.transcribe(captured_audio)
                    t_stt_dur = time.perf_counter() - t_stt_start

                    logger.info(f"🎙️ [Voice WS] Faster-Whisper transcript ({t_stt_dur:.3f}s): '{transcript}'")

                    if not transcript or not transcript.strip():
                        state = "LISTENING"
                        await websocket.send_text(json.dumps({
                            "type": "transcript_empty",
                            "message": "No clear speech detected",
                            "state": state
                        }))
                        continue

                    # Send final transcript to UI
                    await websocket.send_text(json.dumps({
                        "type": "transcript_final",
                        "transcript": transcript,
                        "duration_s": t_stt_dur
                    }))

                    # Load conversation messages from Redis / Postgres
                    messages = await redis_service.get_session_messages(session_id)
                    if messages is None:
                        session = await session_service.get_session(session_id, user_id)
                        messages = (session.get("messages", []) if session else []) or []
                        await redis_service.set_session_messages(session_id, messages)

                    # Execute EXISTING Dolphin Chat Pipeline
                    t_chat_start = time.perf_counter()
                    (
                        node_response,
                        updated_messages,
                        standalone_query,
                        understanding_summary,
                        extras
                    ) = await chat_service.run_chat(
                        user_id=user_id,
                        session_id=session_id,
                        db_messages=messages,
                        current_query=transcript,
                        user_details=user_details
                    )
                    t_chat_dur = time.perf_counter() - t_chat_start
                    logger.info(f"🐬 [Voice WS] Dolphin run_chat finished in {t_chat_dur:.3f}s")

                    # Persist messages in Redis & PostgreSQL
                    await redis_service.set_session_messages(session_id, updated_messages)
                    await session_service.update_session_messages(session_id, updated_messages)

                    # Send full visual response payload to client for chat UI history
                    response_text = node_response.content or ""
                    sections = getattr(node_response, "sections", None) or []
                    suggestions = getattr(node_response, "question_suggestions", None) or []
                    meta = getattr(node_response, "metadata", None) or {}

                    await websocket.send_text(json.dumps({
                        "type": "assistant_text",
                        "user_query": transcript,
                        "content": response_text,
                        "sections": sections,
                        "question_suggestions": suggestions,
                        "metadata": meta,
                        "media": extras if isinstance(extras, dict) else {},
                        "session_id": session_id
                    }))

                    # -----------------------------
                    # PIPER TTS STREAMING
                    # -----------------------------
                    state = "ASSISTANT_SPEAKING"
                    current_tts_cancel_event = asyncio.Event()

                    sentences = TTSNormalizer.split_into_tts_sentences(response_text)
                    await websocket.send_text(json.dumps({
                        "type": "tts_started",
                        "total_sentences": len(sentences),
                        "state": state
                    }))

                    sentence_idx = 0
                    async for idx, sentence_text, wav_bytes in tts_service.generate_sentence_audio_stream(
                        response_text,
                        cancel_event=current_tts_cancel_event
                    ):
                        if current_tts_cancel_event.is_set():
                            break

                        wav_b64 = base64.b64encode(wav_bytes).decode("utf-8")
                        await websocket.send_text(json.dumps({
                            "type": "tts_audio_chunk",
                            "chunk_index": idx,
                            "sentence": sentence_text,
                            "audio": wav_b64
                        }))
                        sentence_idx += 1

                    if not current_tts_cancel_event.is_set():
                        state = "LISTENING"
                        await websocket.send_text(json.dumps({
                            "type": "tts_completed",
                            "total_chunks_sent": sentence_idx,
                            "state": state
                        }))

                # 4. User Interruption (Barge-In)
                elif msg_type == "interrupt":
                    logger.info("⚡ [Voice WS] User interrupted assistant playback.")
                    if current_tts_cancel_event:
                        current_tts_cancel_event.set()
                    audio_buffer.clear()
                    state = "USER_SPEAKING"
                    await websocket.send_text(json.dumps({"type": "interrupted", "state": state}))

                # 5. Session End
                elif msg_type == "session_end":
                    if current_tts_cancel_event:
                        current_tts_cancel_event.set()
                    audio_buffer.clear()
                    state = "IDLE"
                    await websocket.send_text(json.dumps({"type": "session_ended", "state": state}))
                    break

            elif "bytes" in message:
                # Raw binary PCM 16-bit 16kHz audio stream frame
                raw_bytes = message["bytes"]
                if raw_bytes:
                    audio_buffer.extend(raw_bytes)
                    if state != "USER_SPEAKING":
                        state = "USER_SPEAKING"
                        await websocket.send_text(json.dumps({"type": "speech_started", "state": state}))

    except WebSocketDisconnect:
        logger.info(f"🔌 [Voice WS] WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.exception(f"❌ [Voice WS] Error in voice session {session_id}: {e}")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
    finally:
        if current_tts_cancel_event:
            current_tts_cancel_event.set()
