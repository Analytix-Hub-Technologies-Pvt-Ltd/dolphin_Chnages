from __future__ import annotations

import asyncio
import io
import wave
from typing import Optional, Union
import numpy as np
from loguru import logger
from faster_whisper import WhisperModel

from config import settings


class FasterWhisperService:
    """
    Local Faster-Whisper Speech-To-Text Service.

    Key Features:
    - Loaded once as a singleton model cache.
    - Runs on CPU with INT8 quantization for rapid, resource-efficient local transcription.
    - Integrated Silero VAD filtering to reject silence and ambient background noise.
    - Supports audio from raw PCM (16kHz 16-bit mono), WAV bytes, or float32 arrays.
    - Async threadpool execution ensuring no event-loop latency.
    """

    _instance: Optional[FasterWhisperService] = None

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ) -> None:
        self.model_size = model_size or settings.whisper_model
        self.device = device or settings.whisper_device
        self.compute_type = compute_type or settings.whisper_compute_type
        self._model: Optional[WhisperModel] = None

    @classmethod
    def get_instance(cls) -> FasterWhisperService:
        if cls._instance is None:
            cls._instance = FasterWhisperService()
        return cls._instance

    def load_model(self) -> None:
        """Load Faster-Whisper model into memory (sync)."""
        if self._model is not None:
            return

        logger.info(
            f"🎙️ Loading Faster-Whisper model '{self.model_size}' "
            f"(device={self.device}, compute_type={self.compute_type})..."
        )
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            download_root=None,
        )
        logger.success(f"✅ Faster-Whisper model '{self.model_size}' loaded successfully.")

    def _audio_bytes_to_np(self, audio_data: bytes) -> np.ndarray:
        """Convert incoming WAV or raw PCM 16-bit 16kHz mono bytes to normalized float32 numpy array."""
        if audio_data.startswith(b"RIFF"):
            # WAV container
            with wave.open(io.BytesIO(audio_data), "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                framerate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())

            if sample_width == 2:  # 16-bit PCM
                pcm_data = np.frombuffer(frames, dtype=np.int16)
                if channels > 1:
                    pcm_data = pcm_data[::channels]  # Downmix to mono
                return pcm_data.astype(np.float32) / 32768.0
            elif sample_width == 4:  # 32-bit float or int
                pcm_data = np.frombuffer(frames, dtype=np.float32)
                return pcm_data
            else:
                pcm_data = np.frombuffer(frames, dtype=np.int16)
                return pcm_data.astype(np.float32) / 32768.0
        else:
            # Assume raw 16-bit PCM 16kHz mono
            pcm_data = np.frombuffer(audio_data, dtype=np.int16)
            return pcm_data.astype(np.float32) / 32768.0

    def _transcribe_sync(self, audio_input: Union[bytes, np.ndarray]) -> str:
        """Synchronously transcribe audio data using faster-whisper."""
        if self._model is None:
            self.load_model()

        if isinstance(audio_input, bytes):
            if len(audio_input) < 1000:  # Audio too short to contain speech
                return ""
            audio_array = self._audio_bytes_to_np(audio_input)
        elif isinstance(audio_input, np.ndarray):
            audio_array = audio_input
        else:
            return ""

        if len(audio_array) < 1600:  # Less than 100ms
            return ""

        try:
            segments, info = self._model.transcribe(
                audio_array,
                beam_size=3,
                language="en",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400, threshold=0.4),
                temperature=0.0,
            )

            text_parts = [segment.text.strip() for segment in segments if segment.text.strip()]
            transcript = " ".join(text_parts).strip()
            return transcript
        except Exception as e:
            logger.error(f"❌ Faster-Whisper transcription error: {e}")
            return ""

    async def transcribe(self, audio_input: Union[bytes, np.ndarray]) -> str:
        """Asynchronously transcribe audio data."""
        return await asyncio.to_thread(self._transcribe_sync, audio_input)
