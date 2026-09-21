import pytest
import asyncio
from services.tts_service import PiperTTSService
from services.stt_service import FasterWhisperService


@pytest.mark.anyio
async def test_piper_and_whisper_roundtrip():
    tts_service = PiperTTSService.get_instance()
    stt_service = FasterWhisperService.get_instance()

    test_sentence = "Enclosed space entry requires a valid permit and proper ventilation."
    
    # 1. Synthesize with Piper
    wav_bytes = await tts_service.synthesize_sentence(test_sentence)
    assert len(wav_bytes) > 5000, "WAV audio bytes should be produced"

    # 2. Transcribe with Faster-Whisper
    transcript = await stt_service.transcribe(wav_bytes)
    assert transcript, "Transcript should not be empty"

    transcript_lower = transcript.lower()
    assert "enclosed space" in transcript_lower
    assert "permit" in transcript_lower
    assert "ventilation" in transcript_lower
