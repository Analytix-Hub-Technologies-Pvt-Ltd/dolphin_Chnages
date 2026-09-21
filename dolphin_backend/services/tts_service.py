from __future__ import annotations

import asyncio
import io
import os
import wave
from typing import AsyncGenerator, List, Optional
from loguru import logger
import piper

from config import settings
from services.tts_normalizer import TTSNormalizer


class PiperTTSService:
    """
    Local Piper Neural Text-To-Speech Service.

    Key Features:
    - Reusable singleton model instance (no reloading on each turn).
    - Precise speech rate control via length_scale (default ~135 WPM).
    - Threadpool execution to avoid blocking asyncio event loop.
    - Sentence-by-sentence streaming generation.
    - Cooperative cancellation / interruption token support.
    """

    _instance: Optional[PiperTTSService] = None

    def __init__(
        self,
        model_path: Optional[str] = None,
        config_path: Optional[str] = None,
        length_scale: Optional[float] = None,
        noise_scale: Optional[float] = None,
        noise_w: Optional[float] = None,
        speaker_id: Optional[int] = None,
    ) -> None:
        self.model_path = model_path or settings.piper_model_path
        self.config_path = config_path or settings.piper_config_path
        self.length_scale = length_scale if length_scale is not None else settings.piper_length_scale
        self.noise_scale = noise_scale if noise_scale is not None else settings.piper_noise_scale
        self.noise_w = noise_w if noise_w is not None else settings.piper_noise_w
        self.speaker_id = speaker_id if speaker_id is not None else settings.piper_speaker_id

        self._voice: Optional[piper.PiperVoice] = None
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> PiperTTSService:
        if cls._instance is None:
            cls._instance = PiperTTSService()
        return cls._instance

    def load_model(self) -> None:
        """Load Piper ONNX voice model into memory (sync)."""
        if self._voice is not None:
            return

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Piper model file not found at: {self.model_path}")

        logger.info(f"🔊 Loading Piper TTS voice model from '{self.model_path}'...")
        cfg_path = self.config_path if (self.config_path and os.path.exists(self.config_path)) else None
        self._voice = piper.PiperVoice.load(self.model_path, config_path=cfg_path)
        logger.success(f"✅ Piper TTS voice model loaded successfully (sample_rate={self._voice.config.sample_rate}Hz)")

    def _synthesize_sentence_sync(self, sentence: str) -> bytes:
        """Synchronously synthesize a single sentence into WAV bytes."""
        if self._voice is None:
            self.load_model()

        if not sentence or not sentence.strip():
            return b""

        syn_config = piper.SynthesisConfig(
            length_scale=self.length_scale,
            noise_scale=self.noise_scale,
            noise_w_scale=self.noise_w,
            speaker_id=self.speaker_id,
        )

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            self._voice.synthesize_wav(sentence.strip(), wf, syn_config=syn_config)

        return buf.getvalue()

    async def synthesize_sentence(self, sentence: str) -> bytes:
        """Asynchronously synthesize a single sentence into WAV bytes."""
        return await asyncio.to_thread(self._synthesize_sentence_sync, sentence)

    async def generate_sentence_audio_stream(
        self,
        full_text: str,
        cancel_event: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[tuple[int, str, bytes], None]:
        """
        Takes raw markdown response text, normalizes it, splits into sentence chunks,
        and yields (chunk_index, sentence_text, wav_bytes) as each sentence is synthesized.

        Respects `cancel_event` to instantly halt generation on user interruption.
        """
        sentences = TTSNormalizer.split_into_tts_sentences(full_text)
        logger.info(f"🎙️ TTS Normalizer produced {len(sentences)} spoken sentences from response.")

        for idx, sentence in enumerate(sentences):
            if cancel_event and cancel_event.is_set():
                logger.info(f"🛑 TTS generation cancelled at sentence {idx+1}/{len(sentences)} due to interruption.")
                break

            wav_bytes = await self.synthesize_sentence(sentence)
            if cancel_event and cancel_event.is_set():
                break

            if wav_bytes:
                yield (idx, sentence, wav_bytes)
