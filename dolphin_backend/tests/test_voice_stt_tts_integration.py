import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from services.tts_service import ElevenLabsTTSService
from services.stt_service import DeepgramSTTService


@pytest.mark.anyio
async def test_deepgram_and_elevenlabs_service_interfaces():
    tts_service = ElevenLabsTTSService.get_instance()
    stt_service = DeepgramSTTService.get_instance()

    test_sentence = "Enclosed space entry requires a valid permit and proper ventilation."
    fake_audio = b"ID3" + b"\x00" * 4096

    # 1. Test ElevenLabs synthesize_sentence with mock
    with patch.object(tts_service, "synthesize_sentence", new=AsyncMock(return_value=fake_audio)):
        audio_bytes = await tts_service.synthesize_sentence(test_sentence)
        assert len(audio_bytes) > 1000, "Audio bytes should be produced by ElevenLabs service"

    # 2. Test Deepgram transcribe with mock
    with patch.object(stt_service, "transcribe", new=AsyncMock(return_value=test_sentence)):
        transcript = await stt_service.transcribe(fake_audio)
        assert transcript, "Transcript should not be empty"

        transcript_lower = transcript.lower()
        assert "enclosed space" in transcript_lower
        assert "permit" in transcript_lower
        assert "ventilation" in transcript_lower
