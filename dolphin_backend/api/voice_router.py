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
    get_company_store,
    get_transcribe_store,
    get_embedding_service,
    get_openai_service,
)
from core.redis_client import redis_service
from models.database import get_pool
from services.chat_service import ChatService
from services.session_service import SessionService
from services.stt_service import DeepgramSTTService, DeepgramLiveStreamSession
from services.tts_normalizer import TTSNormalizer
from services.tts_service import ElevenLabsTTSService

router = APIRouter(prefix="/ws", tags=["voice"])


async def get_resolved_user_details(pool, user_id: str, client_details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Resolve complete user profile (company_id, company_name, user_courses, role, etc.)
    matching the exact logic from chat_router.py so voice mode has full company data access.
    """
    user_details = dict(client_details or {})

    if user_id and user_id not in ("anonymous", "guest", "test-user"):
        try:
            cached = await redis_service.get_user_details(user_id)
            if cached:
                user_details = {**cached, **user_details}
        except Exception:
            pass

    # Fetch from PostgreSQL users table if company_id or role missing
    if not user_details.get("company_id") and user_id and user_id not in ("anonymous", "guest"):
        try:
            async with pool.acquire() as conn:
                user_row = await conn.fetchrow(
                    "SELECT company_id, company_name, name, email, role, user_type, ship_name, ship_type, user_courses FROM users WHERE id = $1",
                    user_id
                )
                if user_row:
                    row_dict = dict(user_row)
                    user_details.update({
                        "id": user_id,
                        "name": row_dict.get("name") or user_details.get("name", ""),
                        "email": row_dict.get("email") or user_details.get("email", ""),
                        "role": row_dict.get("role") or user_details.get("role", ""),
                        "user_type": row_dict.get("user_type") or user_details.get("user_type", ""),
                        "company_id": str(row_dict.get("company_id")) if row_dict.get("company_id") else None,
                        "company_name": row_dict.get("company_name") or user_details.get("company_name", ""),
                        "ship_name": row_dict.get("ship_name") or user_details.get("ship_name", ""),
                        "ship_type": row_dict.get("ship_type") or user_details.get("ship_type", ""),
                        "user_courses": row_dict.get("user_courses") or user_details.get("user_courses"),
                    })
                    try:
                        existing_cached = await redis_service.get_user_data(user_id)
                        if existing_cached and existing_cached.get("company_courses"):
                            user_details["company_courses"] = existing_cached["company_courses"]
                        await redis_service.set_user_data(user_id, user_details)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"⚠️ [Voice WS] Failed to fetch user details from PostgreSQL: {e}")

    # Dynamic resolution: if user has company_name but missing company_id, resolve from DB
    if not user_details.get("company_id") and user_details.get("company_name"):
        try:
            async with pool.acquire() as conn:
                cid_row = await conn.fetchrow(
                    "SELECT company_id FROM users WHERE LOWER(company_name) = LOWER($1) AND company_id IS NOT NULL LIMIT 1",
                    user_details.get("company_name")
                )
                if cid_row and cid_row.get("company_id"):
                    user_details["company_id"] = str(cid_row["company_id"])
                    logger.info(f"✅ [Voice WS] Dynamically resolved company_id: {user_details['company_id']} for {user_details.get('company_name')}")
        except Exception as e:
            logger.warning(f"⚠️ [Voice WS] Could not dynamically resolve company_id: {e}")

    # Fallback to active company in company_documents if available
    if not user_details.get("company_id"):
        try:
            async with pool.acquire() as conn:
                doc_row = await conn.fetchrow("SELECT company_id FROM company_documents WHERE is_active = true LIMIT 1")
                if doc_row and doc_row.get("company_id"):
                    user_details["company_id"] = str(doc_row["company_id"])
                    logger.info(f"✅ [Voice WS] Fallback company_id assigned: {user_details['company_id']}")
        except Exception as e:
            logger.debug(f"[Voice WS] Fallback company check bypassed: {e}")

    return user_details


@router.websocket("/voice/{session_id}")
async def voice_websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Real-Time WebSocket Voice Assistant Endpoint using Deepgram & ElevenLabs.

    Flow:
    1. Client connects with session_id.
    2. Opens persistent Deepgram Live Stream WebSocket session (Nova-3).
    3. Streams 16kHz PCM audio chunks to Deepgram, emitting interim & final transcripts.
    4. Passes final transcript directly to ChatService on the client.
    5. Sends full unaltered Dolphin response to UI for rich chat history.
    6. Normalizes response text for speech and generates streaming sentence-level ElevenLabs TTS audio.
    7. Supports instant interruption (barge-in) and continuous multi-turn conversation.
    """
    await websocket.accept()
    logger.info(f"🎙️ [Voice WS] Connection established for session: {session_id}")

    pool = await get_pool()
    session_service = SessionService(pool)
    openai_service = get_openai_service()
    embedder = get_embedding_service(openai_service)
    store = get_faiss_store()
    company_store = get_company_store()
    transcribe_store = get_transcribe_store()

    chat_service = ChatService(
        openai_service,
        embedder,
        store,
        session_service,
        company_store=company_store,
        transcribe_store=transcribe_store,
    )
    stt_service = DeepgramSTTService.get_instance()
    tts_service = ElevenLabsTTSService.get_instance()

    user_id = "test-user"
    user_details = {}
    audio_buffer = bytearray()
    current_tts_cancel_event: Optional[asyncio.Event] = None
    turn_lock = asyncio.Lock()
    state = "IDLE"
    last_transcript_time = 0.0
    utterance_finalized = False

    # Deepgram Live Session
    deepgram_session: Optional[DeepgramLiveStreamSession] = None
    loop = asyncio.get_running_loop()

    def handle_partial_transcript(partial: str):
        if not partial or not partial.strip():
            return
        asyncio.run_coroutine_threadsafe(
            websocket.send_text(
                json.dumps({
                    "type": "transcript_partial",
                    "transcript": partial,
                    "state": "USER_SPEAKING"
                })
            ),
            loop
        )

    def handle_final_transcript(transcript: str, duration_s: float):
        nonlocal last_transcript_time, state, utterance_finalized
        if not transcript or not transcript.strip():
            return
        utterance_finalized = True
        last_transcript_time = time.perf_counter()
        state = "PROCESSING"
        logger.info(f"🎙️ [Voice WS] Deepgram final transcript ({duration_s:.3f}s): '{transcript}'")
        asyncio.run_coroutine_threadsafe(
            websocket.send_text(
                json.dumps({
                    "type": "transcript_final",
                    "transcript": transcript,
                    "duration_s": duration_s,
                    "state": "PROCESSING"
                })
            ),
            loop
        )

    async def init_deepgram_stream():
        nonlocal deepgram_session
        if deepgram_session and deepgram_session.is_connected:
            return
        if stt_service.is_configured:
            deepgram_session = stt_service.create_live_stream_session(
                on_partial_transcript=handle_partial_transcript,
                on_final_transcript=handle_final_transcript,
                sample_rate=16000,
            )
            await deepgram_session.start()

    try:
        # Load active session details
        try:
            stored_user = await redis_service.get_active_session(session_id)
            if stored_user:
                user_id = stored_user
            user_details = await get_resolved_user_details(pool, user_id)
        except Exception as e:
            logger.warning(f"⚠️ [Voice WS] Session/User lookup warning: {e}")

        state = "LISTENING"
        await init_deepgram_stream()

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
                    client_details = payload.get("user_details") or {}
                    user_details = await get_resolved_user_details(pool, user_id, client_details)
                    logger.info(f"🎙️ [Voice WS] voice_start initialized: user_id={user_id}, company_id={user_details.get('company_id')}, company_name={user_details.get('company_name')}")

                    audio_buffer.clear()
                    utterance_finalized = False
                    if deepgram_session:
                        deepgram_session.reset_utterance()
                    state = "LISTENING"
                    await init_deepgram_stream()
                    await websocket.send_text(json.dumps({"type": "listening", "state": state}))

                # 1b. Microphone Mute / Unmute notification from client
                elif msg_type == "mute":
                    is_muted = payload.get("is_muted", False)
                    logger.info(f"🎙️ [Voice WS] Client mute state changed: is_muted={is_muted}")
                    audio_buffer.clear()
                    utterance_finalized = False
                    if is_muted:
                        state = "LISTENING"
                        await websocket.send_text(json.dumps({"type": "listening", "state": state, "is_muted": True}))

                # 2. Audio Chunk (Base64 JSON encoded)
                elif msg_type == "audio_chunk":
                    if state in ("ASSISTANT_SPEAKING", "PROCESSING") or state not in ("LISTENING", "USER_SPEAKING") or turn_lock.locked():
                        continue

                    chunk_b64 = payload.get("data", "")
                    if chunk_b64:
                        chunk_bytes = base64.b64decode(chunk_b64)
                        audio_buffer.extend(chunk_bytes)
                        if deepgram_session and deepgram_session.is_connected:
                            await deepgram_session.send_audio(chunk_bytes)
                        if state != "USER_SPEAKING":
                            state = "USER_SPEAKING"
                            utterance_finalized = False
                            await websocket.send_text(json.dumps({"type": "speech_started", "state": state}))

                # 3. Speech End / VAD Silence Detected -> Process Audio
                elif msg_type == "speech_end":
                    if state not in ("LISTENING", "USER_SPEAKING") or turn_lock.locked():
                        continue

                    captured_audio = bytes(audio_buffer) if audio_buffer else b""
                    audio_buffer.clear()

                    if deepgram_session and deepgram_session.is_connected:
                        await deepgram_session.finish_utterance()

                    # Only run REST fallback if Deepgram live stream has not already emitted a final transcript
                    if not utterance_finalized:
                        if len(captured_audio) >= 3200:  # >= 200ms
                            state = "PROCESSING"
                            await websocket.send_text(json.dumps({"type": "processing_started", "state": state}))
                            t_stt_start = time.perf_counter()
                            transcript = await stt_service.transcribe(captured_audio)
                            t_stt_dur = time.perf_counter() - t_stt_start
                            if transcript and transcript.strip():
                                utterance_finalized = True
                                last_transcript_time = time.perf_counter()
                                await websocket.send_text(json.dumps({
                                    "type": "transcript_final",
                                    "transcript": transcript,
                                    "duration_s": t_stt_dur,
                                    "state": "PROCESSING"
                                }))
                            else:
                                state = "LISTENING"
                                await websocket.send_text(json.dumps({
                                    "type": "transcript_empty",
                                    "message": "No clear speech detected",
                                    "state": state
                                }))
                        else:
                            state = "LISTENING"
                            await websocket.send_text(json.dumps({
                                "type": "transcript_empty",
                                "message": "No audio captured",
                                "state": state
                            }))

                # 4a. Incremental Real-Time Sentence-by-Sentence TTS Request
                elif msg_type == "tts_sentence":
                    sentence_text = payload.get("sentence", "")
                    chunk_idx = payload.get("chunk_index", 0)
                    is_last = payload.get("is_last", False)
                    if sentence_text and sentence_text.strip():
                        state = "ASSISTANT_SPEAKING"
                        if current_tts_cancel_event is None or current_tts_cancel_event.is_set():
                            current_tts_cancel_event = asyncio.Event()

                        try:
                            clean_sentences = TTSNormalizer.split_into_tts_sentences(sentence_text)
                            for sub_idx, sub_s in enumerate(clean_sentences):
                                if current_tts_cancel_event and current_tts_cancel_event.is_set():
                                    break
                                audio_bytes = await tts_service.synthesize_sentence(
                                    sub_s,
                                    cancel_event=current_tts_cancel_event
                                )
                                if audio_bytes and not (current_tts_cancel_event and current_tts_cancel_event.is_set()):
                                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                                    await websocket.send_text(json.dumps({
                                        "type": "tts_audio_chunk",
                                        "chunk_index": chunk_idx,
                                        "sub_index": sub_idx,
                                        "sentence": sub_s,
                                        "audio": audio_b64,
                                        "is_last": is_last and (sub_idx == len(clean_sentences) - 1)
                                    }))
                        except Exception as e:
                            logger.exception(f"❌ [Voice WS] ElevenLabs TTS sentence synthesis failed: {e}")

                    if is_last:
                        await websocket.send_text(json.dumps({
                            "type": "tts_completed",
                            "state": "ASSISTANT_SPEAKING"
                        }))

                # 4b. Full-Text Fallback TTS Request for Normal Chat Response
                elif msg_type == "tts_request":
                    text_to_speak = payload.get("text", "")
                    if text_to_speak:
                        state = "ASSISTANT_SPEAKING"
                        current_tts_cancel_event = asyncio.Event()

                        sentences = TTSNormalizer.split_into_tts_sentences(text_to_speak)
                        await websocket.send_text(json.dumps({
                            "type": "tts_started",
                            "total_sentences": len(sentences),
                            "state": state
                        }))

                        sentence_idx = 0
                        if sentences:
                            try:
                                async for idx, sentence_text, audio_bytes in tts_service.generate_sentence_audio_stream(
                                    text_to_speak,
                                    cancel_event=current_tts_cancel_event
                                ):
                                    if current_tts_cancel_event.is_set():
                                        break

                                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                                    await websocket.send_text(json.dumps({
                                        "type": "tts_audio_chunk",
                                        "chunk_index": idx,
                                        "sentence": sentence_text,
                                        "audio": audio_b64
                                    }))
                                    sentence_idx += 1
                            except Exception as e:
                                logger.exception(f"❌ [Voice WS] ElevenLabs TTS streaming failed: {e}")

                        if not current_tts_cancel_event.is_set():
                            if sentence_idx == 0:
                                state = "LISTENING"
                                await websocket.send_text(json.dumps({
                                    "type": "tts_completed",
                                    "total_chunks_sent": 0,
                                    "state": state
                                }))
                            else:
                                state = "ASSISTANT_SPEAKING"
                                await websocket.send_text(json.dumps({
                                    "type": "tts_completed",
                                    "total_chunks_sent": sentence_idx,
                                    "state": state
                                }))

                # 5. Client Finished Physical Audio Playback through Speakers
                elif msg_type == "playback_finished":
                    logger.info(f"🏁 [Voice WS] Client finished audio playback. Re-arming microphone for session: {session_id}")
                    audio_buffer.clear()
                    utterance_finalized = False
                    if deepgram_session:
                        deepgram_session.reset_utterance()
                    state = "LISTENING"
                    await websocket.send_text(json.dumps({"type": "listening", "state": state}))

                # 5b. User Interruption (Barge-In)
                elif msg_type == "interrupt":
                    logger.info("⚡ [Voice WS] User interrupted assistant playback.")
                    if current_tts_cancel_event:
                        current_tts_cancel_event.set()
                    audio_buffer.clear()
                    utterance_finalized = False
                    if deepgram_session:
                        deepgram_session.reset_utterance()
                    state = "USER_SPEAKING"
                    await websocket.send_text(json.dumps({"type": "interrupted", "state": state}))

                # 6. Session End
                elif msg_type == "session_end":
                    if current_tts_cancel_event:
                        current_tts_cancel_event.set()
                    audio_buffer.clear()
                    utterance_finalized = False
                    state = "IDLE"
                    await websocket.send_text(json.dumps({"type": "session_ended", "state": state}))
                    break

            elif "bytes" in message:
                # Raw binary PCM 16-bit 16kHz audio stream frame from browser
                if state in ("ASSISTANT_SPEAKING", "PROCESSING") or state not in ("LISTENING", "USER_SPEAKING") or turn_lock.locked():
                    continue

                raw_bytes = message["bytes"]
                if raw_bytes:
                    audio_buffer.extend(raw_bytes)
                    if deepgram_session and deepgram_session.is_connected:
                        await deepgram_session.send_audio(raw_bytes)
                    if state != "USER_SPEAKING":
                        state = "USER_SPEAKING"
                        utterance_finalized = False
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
        if deepgram_session:
            await deepgram_session.close()
