from __future__ import annotations

import asyncio
import io
import inspect
import json
import time
import wave
from typing import AsyncGenerator, Callable, Dict, Optional, Union
import httpx
from loguru import logger
import websockets

from config import settings


class DeepgramSTTService:
    """
    Cloud-Based Real-Time Streaming Speech-To-Text Service using Deepgram.

    Key Features:
    - Persistent live streaming session over WebSocket (`wss://api.deepgram.com/v1/listen`).
    - Low-latency real-time interim results (partials) and final speech transcripts.
    - Deepgram Nova-3 speech model with smart formatting and maritime domain boosting.
    - Built-in Voice Activity Detection & Endpointing (350ms silence detection).
    - REST fallback transcription for pre-recorded or buffered audio frames.
    - Precise latency measurement and error handling.
    """

    _instance: Optional[DeepgramSTTService] = None

    # High-value maritime and company SMS terms to boost recognition accuracy
    MARITIME_KEYWORDS = (
        "SOLAS:2,MARPOL:2,STCW:2,ISM:2,SMS:2,MoC:2,Management of Change:2,"
        "ECDIS:2,bunker:2,bilge:2,ballast:2,enclosed space:2,permit to work:2,"
        "cargo:2,vessel:2,bulk carrier:2,container:2,superintendent:2,"
        "chief engineer:2,master:2,officer:2,navigation:2,liferaft:2,"
        "lifeboat:2,fire drill:2,audit:2,checklist:2,Dolphin:2,maritime:2"
    )

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or settings.deepgram_api_key
        self.model = model or settings.deepgram_model or "nova-3"

    @classmethod
    def get_instance(cls) -> DeepgramSTTService:
        if cls._instance is None:
            cls._instance = DeepgramSTTService()
        return cls._instance

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    @staticmethod
    def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
        """Wrap raw linear16 PCM bytes in standard WAV container header."""
        if pcm_bytes.startswith(b"RIFF"):
            return pcm_bytes
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    async def transcribe_buffer(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe a complete buffer of audio bytes using Deepgram REST API.
        Used as fallback or for direct audio chunks.
        """
        if not self.is_configured:
            logger.warning("⚠️ Deepgram API key is not configured. Returning empty transcript.")
            return ""

        if not audio_data or len(audio_data) < 1600:  # < 100ms
            return ""

        wav_bytes = self._pcm_to_wav(audio_data, sample_rate)
        url = (
            f"https://api.deepgram.com/v1/listen"
            f"?model={self.model}"
            f"&smart_format=true"
            f"&punctuate=true"
            f"&filler_words=false"
            f"&language=en"
            f"&keywords={self.MARITIME_KEYWORDS}"
        )

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav",
        }

        t_start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=headers, content=wav_bytes)
                if response.status_code != 200 and self.model != "nova-2":
                    # Retry with nova-2 fallback if nova-3 is restricted
                    logger.warning(f"⚠️ Deepgram {self.model} returned {response.status_code}. Retrying with nova-2...")
                    fallback_url = f"https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&punctuate=true&language=en"
                    response = await client.post(fallback_url, headers=headers, content=wav_bytes)

                if response.status_code != 200:
                    logger.error(f"❌ Deepgram REST API returned {response.status_code}: {response.text}")
                    return ""

                result = response.json()
                results_obj = result.get("results") if isinstance(result, dict) else {}
                channels = results_obj.get("channels") if isinstance(results_obj, dict) else []
                if channels and isinstance(channels, list) and len(channels) > 0:
                    ch0 = channels[0] if isinstance(channels[0], dict) else {}
                    alts = ch0.get("alternatives") if isinstance(ch0, dict) else []
                    if alts and isinstance(alts, list) and len(alts) > 0:
                        alt0 = alts[0] if isinstance(alts[0], dict) else {}
                        transcript = alt0.get("transcript", "").strip() if isinstance(alt0, dict) else ""
                        dur = time.perf_counter() - t_start
                        if transcript:
                            logger.info(f"🎙️ Deepgram REST transcript ({dur:.3f}s): '{transcript}'")
                        return transcript
                return ""
        except Exception as e:
            logger.exception(f"❌ Deepgram REST transcription error: {e}")
            return ""

    async def transcribe(self, audio_input: Union[bytes, io.BytesIO]) -> str:
        """
        Convenience method to transcribe audio bytes or BytesIO stream.
        """
        if isinstance(audio_input, io.BytesIO):
            audio_bytes = audio_input.getvalue()
        elif isinstance(audio_input, bytes):
            audio_bytes = audio_input
        else:
            return ""
        return await self.transcribe_buffer(audio_bytes)

    def create_live_stream_session(
        self,
        on_partial_transcript: Optional[Callable[[str], None]] = None,
        on_final_transcript: Optional[Callable[[str, float], None]] = None,
        on_utterance_end: Optional[Callable[[], None]] = None,
        sample_rate: int = 16000,
    ) -> DeepgramLiveStreamSession:
        """
        Create a new persistent live streaming session connected directly to Deepgram WebSocket.
        """
        return DeepgramLiveStreamSession(
            api_key=self.api_key,
            model=self.model,
            sample_rate=sample_rate,
            on_partial_transcript=on_partial_transcript,
            on_final_transcript=on_final_transcript,
            on_utterance_end=on_utterance_end,
        )


class DeepgramLiveStreamSession:
    """
    Manages a single real-time bidirectional WebSocket connection to Deepgram.
    
    Streams raw 16kHz PCM audio chunks to Deepgram and receives interim and
    final transcription events in real time with maritime keyterm boosting.
    """

    MARITIME_KEYWORDS = (
        "SOLAS:2,MARPOL:2,STCW:2,ISM:2,SMS:2,MoC:2,Management of Change:2,"
        "ECDIS:2,bunker:2,bilge:2,ballast:2,enclosed space:2,permit to work:2,"
        "cargo:2,vessel:2,bulk carrier:2,container:2,superintendent:2,"
        "chief engineer:2,master:2,officer:2,navigation:2,liferaft:2,"
        "lifeboat:2,fire drill:2,audit:2,checklist:2,Dolphin:2,maritime:2"
    )

    def __init__(
        self,
        api_key: str,
        model: str = "nova-3",
        sample_rate: int = 16000,
        on_partial_transcript: Optional[Callable[[str], None]] = None,
        on_final_transcript: Optional[Callable[[str, float], None]] = None,
        on_utterance_end: Optional[Callable[[], None]] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.sample_rate = sample_rate
        self.on_partial_transcript = on_partial_transcript
        self.on_final_transcript = on_final_transcript
        self.on_utterance_end = on_utterance_end

        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._is_active = False
        self._session_start_time = time.perf_counter()
        self._utterance_start_time = time.perf_counter()
        self._accumulated_finals: list[str] = []
        self._latest_interim: str = ""
        self._utterance_finalized: bool = False

    @property
    def is_connected(self) -> bool:
        return self.ws is not None and self._is_active

    def reset_utterance(self) -> None:
        """Reset state for a fresh speech utterance turn."""
        self._accumulated_finals = []
        self._latest_interim = ""
        self._utterance_finalized = False
        self._utterance_start_time = time.perf_counter()

    async def start(self) -> bool:
        """Connect to Deepgram streaming WebSocket endpoint."""
        if not self.api_key:
            logger.warning("⚠️ Deepgram API key missing for live stream session.")
            return False

        ws_url = (
            f"wss://api.deepgram.com/v1/listen"
            f"?model={self.model}"
            f"&language=en"
            f"&smart_format=true"
            f"&punctuate=true"
            f"&filler_words=false"
            f"&interim_results=true"
            f"&endpointing=350"
            f"&utterance_end_ms=1000"
            f"&vad_events=true"
            f"&encoding=linear16"
            f"&sample_rate={self.sample_rate}"
            f"&channels=1"
            f"&keywords={self.MARITIME_KEYWORDS}"
        )
        headers = {
            "Authorization": f"Token {self.api_key}"
        }

        connect_kwargs = {
            "ping_interval": 20,
            "ping_timeout": 20,
        }

        # Compatible with websockets >= 14 (additional_headers) and websockets < 14 (extra_headers)
        try:
            sig = inspect.signature(websockets.connect)
            if "additional_headers" in sig.parameters:
                connect_kwargs["additional_headers"] = headers
            else:
                connect_kwargs["extra_headers"] = headers
        except Exception:
            connect_kwargs["additional_headers"] = headers

        try:
            logger.info(f"🎙️ Connecting to Deepgram Live Stream WebSocket (model={self.model})...")
            self.ws = await websockets.connect(
                ws_url,
                **connect_kwargs
            )
            self._is_active = True
            self._session_start_time = time.perf_counter()
            self.reset_utterance()
            self._receive_task = asyncio.create_task(self._receive_loop())
            logger.success(f"✅ Deepgram Live Stream WebSocket connected successfully ({self.model}).")
            return True
        except Exception as e:
            # Fallback to nova-2 if nova-3 fails to connect
            if self.model != "nova-2":
                logger.warning(f"⚠️ Failed to connect to Deepgram with model={self.model}: {e}. Retrying with nova-2...")
                self.model = "nova-2"
                return await self.start()

            logger.error(f"❌ Failed to connect to Deepgram Live Stream: {e}")
            self._is_active = False
            self.ws = None
            return False

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Send raw 16kHz 16-bit PCM audio bytes to Deepgram."""
        if self.ws and self._is_active:
            try:
                await self.ws.send(audio_chunk)
            except Exception as e:
                logger.warning(f"⚠️ Error sending audio chunk to Deepgram: {e}")

    def _flush_final_transcript(self) -> None:
        """Flush accumulated finalized segments or latest interim to final callback."""
        candidate_text = ""
        if self._accumulated_finals:
            candidate_text = " ".join(self._accumulated_finals).strip()
            self._accumulated_finals = []
            self._latest_interim = ""
        elif self._latest_interim and self._latest_interim.strip():
            candidate_text = self._latest_interim.strip()
            self._latest_interim = ""

        if candidate_text:
            self._utterance_finalized = True
            dur = time.perf_counter() - self._utterance_start_time
            self._utterance_start_time = time.perf_counter()
            if self.on_final_transcript:
                logger.info(f"🎙️ [Deepgram Live] Emitting final transcript ({dur:.3f}s): '{candidate_text}'")
                self.on_final_transcript(candidate_text, dur)

    async def _receive_loop(self) -> None:
        """Listen for transcription events from Deepgram."""
        if not self.ws:
            return

        try:
            async for message in self.ws:
                if not self._is_active:
                    break

                try:
                    data = json.loads(message)
                except Exception:
                    continue

                if not isinstance(data, dict):
                    continue

                msg_type = data.get("type")
                if msg_type == "UtteranceEnd":
                    self._flush_final_transcript()
                    if self.on_utterance_end:
                        self.on_utterance_end()
                    continue

                if msg_type != "Results":
                    continue

                # Safely extract channel dict
                channel_raw = data.get("channel")
                channel_dict = {}
                if isinstance(channel_raw, list) and len(channel_raw) > 0:
                    channel_dict = channel_raw[0] if isinstance(channel_raw[0], dict) else {}
                elif isinstance(channel_raw, dict):
                    channel_dict = channel_raw
                else:
                    results_channels = data.get("results", {}).get("channels", []) if isinstance(data.get("results"), dict) else []
                    if isinstance(results_channels, list) and len(results_channels) > 0:
                        channel_dict = results_channels[0] if isinstance(results_channels[0], dict) else {}

                alternatives = channel_dict.get("alternatives", []) if isinstance(channel_dict, dict) else []
                if not isinstance(alternatives, list) or len(alternatives) == 0:
                    continue

                alt0 = alternatives[0] if isinstance(alternatives[0], dict) else {}
                transcript = alt0.get("transcript", "").strip() if isinstance(alt0, dict) else ""
                is_final = bool(data.get("is_final", False))
                speech_final = bool(data.get("speech_final", False))

                if transcript:
                    if is_final:
                        self._accumulated_finals.append(transcript)
                        self._latest_interim = ""
                        if speech_final:
                            self._flush_final_transcript()
                        else:
                            # Send partial preview with accumulated text
                            if self.on_partial_transcript:
                                current_preview = " ".join(self._accumulated_finals).strip()
                                self.on_partial_transcript(current_preview)
                    else:
                        # Interim partial transcript
                        self._latest_interim = transcript
                        if self.on_partial_transcript:
                            current_preview = " ".join(self._accumulated_finals + [transcript]).strip()
                            self.on_partial_transcript(current_preview)

        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"🔌 Deepgram Live WebSocket closed: {e}")
        except Exception as e:
            logger.exception(f"❌ Error in Deepgram receive loop: {e}")
        finally:
            self._is_active = False

    async def finish_utterance(self) -> None:
        """Tell Deepgram current utterance has finished and flush results."""
        if self.ws and self._is_active:
            try:
                await self.ws.send(json.dumps({"type": "Finalize"}))
                # Wait briefly for finalize packet to be processed by Deepgram
                await asyncio.sleep(0.08)
                self._flush_final_transcript()
            except Exception:
                self._flush_final_transcript()

    async def close(self) -> None:
        """Cleanly close the Deepgram WebSocket stream."""
        self._is_active = False
        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None

        if self.ws:
            try:
                await self.ws.send(json.dumps({"type": "CloseStream"}))
                await self.ws.close()
            except Exception:
                pass
            self.ws = None
        logger.info("🔌 Deepgram Live Stream session closed.")
