from __future__ import annotations

import asyncio
import io
import time
from typing import AsyncGenerator, List, Optional
import httpx
from loguru import logger

from config import settings
from services.tts_normalizer import TTSNormalizer


class ElevenLabsTTSService:
    """
    Cloud-Based Real-Time Streaming Text-To-Speech Service using ElevenLabs.

    Key Features:
    - Low-latency sentence-by-sentence streaming synthesis via ElevenLabs `/v1/text-to-speech/{voice_id}/stream`.
    - Turbo model (`eleven_turbo_v2_5` or `eleven_flash_v2`) with `optimize_streaming_latency=4` for ~150-250ms TTFB.
    - Full cooperative cancellation (`cancel_event`) for instant barge-in / interruption handling.
    - Integrated with `TTSNormalizer` to speak clean natural text without reading Markdown/tables/citations.
    - Async HTTP connection pooling via `httpx.AsyncClient`.
    """

    _instance: Optional[ElevenLabsTTSService] = None

    DEFAULT_VOICE_ID = "Xb7hH8MSUJpSbSDYk0k2"  # Alice (High quality premade conversational voice)

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        optimize_latency: Optional[int] = None,
    ) -> None:
        self.api_key = api_key or settings.elevenlabs_api_key
        raw_vid = voice_id or settings.elevenlabs_voice_id or self.DEFAULT_VOICE_ID
        # Sanitize voice_id: if user accidentally passed an API key (starts with sk_) or invalid ID, fallback to Alice
        if not raw_vid or raw_vid.startswith("sk_") or raw_vid == "21m00Tcm4TlvDq8ikWAM":
            self.voice_id = self.DEFAULT_VOICE_ID
        else:
            self.voice_id = raw_vid

        self.model_id = model_id or settings.elevenlabs_model_id or "eleven_turbo_v2_5"
        self.optimize_latency = optimize_latency if optimize_latency is not None else settings.elevenlabs_optimize_latency

    @classmethod
    def get_instance(cls) -> ElevenLabsTTSService:
        if cls._instance is None:
            cls._instance = ElevenLabsTTSService()
        else:
            # Sync any runtime settings changes
            cls._instance.api_key = settings.elevenlabs_api_key or cls._instance.api_key
            raw_vid = settings.elevenlabs_voice_id or cls._instance.voice_id
            if raw_vid and not raw_vid.startswith("sk_") and raw_vid != "21m00Tcm4TlvDq8ikWAM":
                cls._instance.voice_id = raw_vid
            else:
                cls._instance.voice_id = cls.DEFAULT_VOICE_ID
        return cls._instance

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def synthesize_sentence(
        self,
        sentence: str,
        cancel_event: Optional[asyncio.Event] = None
    ) -> bytes:
        """
        Synthesize a single spoken sentence into audio bytes (MP3 format).
        Aborts immediately if `cancel_event` is triggered.
        """
        if not self.is_configured:
            logger.warning("⚠️ ElevenLabs API key is not configured.")
            return b""

        if not sentence or not sentence.strip():
            return b""

        clean_text = TTSNormalizer.normalize_for_tts(sentence)
        if not clean_text or not clean_text.strip():
            return b""

        if cancel_event and cancel_event.is_set():
            return b""

        # Ensure voice_id is clean
        if not self.voice_id or self.voice_id.startswith("sk_") or self.voice_id == "21m00Tcm4TlvDq8ikWAM":
            self.voice_id = self.DEFAULT_VOICE_ID

        params = {
            "optimize_streaming_latency": self.optimize_latency,
            "output_format": "mp3_44100_128"
        }
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": clean_text.strip(),
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }

        t_start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"
                async with client.stream("POST", url, params=params, headers=headers, json=payload) as response:
                    if response.status_code == 404:
                        err_body = await response.aread()
                        logger.warning(f"⚠️ Voice '{self.voice_id}' not found (404). Falling back to default voice '{self.DEFAULT_VOICE_ID}'...")
                        self.voice_id = self.DEFAULT_VOICE_ID
                        # Retry once with default voice
                        url_fallback = f"https://api.elevenlabs.io/v1/text-to-speech/{self.DEFAULT_VOICE_ID}/stream"
                        async with client.stream("POST", url_fallback, params=params, headers=headers, json=payload) as retry_resp:
                            if retry_resp.status_code != 200:
                                retry_err = await retry_resp.aread()
                                logger.error(f"❌ ElevenLabs TTS retry returned {retry_resp.status_code}: {retry_err.decode('utf-8', errors='ignore')}")
                                return b""
                            chunks = []
                            async for chunk in retry_resp.aiter_bytes():
                                if cancel_event and cancel_event.is_set():
                                    return b""
                                if chunk:
                                    chunks.append(chunk)
                            audio_bytes = b"".join(chunks)
                            dur = time.perf_counter() - t_start
                            logger.info(f"🔊 ElevenLabs synthesized sentence via fallback voice ({dur:.3f}s, {len(audio_bytes)} bytes): '{clean_text[:40]}...'")
                            return audio_bytes

                    elif response.status_code != 200:
                        err_body = await response.aread()
                        logger.error(f"❌ ElevenLabs TTS returned {response.status_code}: {err_body.decode('utf-8', errors='ignore')}")
                        return b""

                    chunks = []
                    async for chunk in response.aiter_bytes():
                        if cancel_event and cancel_event.is_set():
                            logger.info("🛑 ElevenLabs synthesis stream aborted by cancel_event.")
                            return b""
                        if chunk:
                            chunks.append(chunk)

                    audio_bytes = b"".join(chunks)
                    dur = time.perf_counter() - t_start
                    logger.info(f"🔊 ElevenLabs synthesized sentence ({dur:.3f}s, {len(audio_bytes)} bytes): '{clean_text[:40]}...'")
                    return audio_bytes

        except httpx.RequestError as e:
            if cancel_event and cancel_event.is_set():
                return b""
            logger.exception(f"❌ ElevenLabs request error: {e}")
            return b""
        except Exception as e:
            if cancel_event and cancel_event.is_set():
                return b""
            logger.exception(f"❌ ElevenLabs synthesis error: {e}")
            return b""

    async def generate_sentence_audio_stream(
        self,
        full_text: str,
        cancel_event: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[tuple[int, str, bytes], None]:
        """
        Takes raw markdown response text, normalizes it, splits into sentence chunks,
        and yields (chunk_index, sentence_text, mp3_audio_bytes) as each sentence is synthesized.

        Respects `cancel_event` to instantly halt generation on user interruption.
        """
        sentences = TTSNormalizer.split_into_tts_sentences(full_text)
        logger.info(f"🎙️ TTS Normalizer produced {len(sentences)} spoken sentences from response.")

        for idx, sentence in enumerate(sentences):
            if cancel_event and cancel_event.is_set():
                logger.info(f"🛑 ElevenLabs TTS generation cancelled at sentence {idx+1}/{len(sentences)} due to interruption.")
                break

            audio_bytes = await self.synthesize_sentence(sentence, cancel_event=cancel_event)
            if cancel_event and cancel_event.is_set():
                break

            if audio_bytes:
                yield (idx, sentence, audio_bytes)
