import json
import base64
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from starlette.testclient import TestClient
from api.voice_router import router as voice_router
from models.node_response import NodeResponse
from services.stt_service import DeepgramSTTService
from services.tts_service import ElevenLabsTTSService


def test_voice_router_websocket_deepgram_and_elevenlabs_flow():
    test_app = FastAPI()
    test_app.include_router(voice_router)

    audio_bytes = b"\x00" * 8192

    mock_pool = MagicMock()
    mock_stt = MagicMock()
    mock_stt.is_configured = False
    mock_stt.transcribe = AsyncMock(return_value="What is enclosed space entry?")

    async def mock_tts_stream(text, cancel_event=None):
        yield (0, "Enclosed space entry requires a valid permit.", audio_bytes)

    mock_tts = MagicMock()
    mock_tts.is_configured = True
    mock_tts.generate_sentence_audio_stream = mock_tts_stream
    mock_tts.synthesize_sentence = AsyncMock(return_value=audio_bytes)

    with patch("api.voice_router.get_pool", new_callable=AsyncMock) as mock_get_pool, \
         patch("api.voice_router.get_embedding_service", return_value=MagicMock()), \
         patch("api.voice_router.get_faiss_store", return_value=MagicMock()), \
         patch("api.voice_router.get_openai_service", return_value=MagicMock()), \
         patch("api.voice_router.DeepgramSTTService.get_instance", return_value=mock_stt), \
         patch("api.voice_router.ElevenLabsTTSService.get_instance", return_value=mock_tts), \
         patch("api.voice_router.redis_service.get_active_session", new_callable=AsyncMock) as mock_get_sess, \
         patch("api.voice_router.redis_service.get_user_details", new_callable=AsyncMock) as mock_get_user:

        mock_get_pool.return_value = mock_pool
        mock_get_sess.return_value = "test-user"
        mock_get_user.return_value = {"role": "Chief Officer"}

        client = TestClient(test_app)
        with client.websocket_connect("/ws/voice/test-voice-session-001") as websocket:
            # 1. Receive session_started
            init_data = websocket.receive_json()
            assert init_data["type"] == "session_started"
            assert init_data["state"] == "LISTENING"

            # 2. Send audio chunk (base64 PCM)
            b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
            websocket.send_json({
                "type": "audio_chunk",
                "data": b64_audio
            })

            # Receive speech_started
            speech_msg = websocket.receive_json()
            assert speech_msg["type"] == "speech_started"

            # 3. Send speech_end
            websocket.send_json({
                "type": "speech_end"
            })

            # 4. Receive processing_started
            proc_msg = websocket.receive_json()
            assert proc_msg["type"] == "processing_started"

            # 5. Receive transcript_final
            trans_msg = websocket.receive_json()
            assert trans_msg["type"] == "transcript_final"
            assert "enclosed space" in trans_msg["transcript"].lower()

            # 6. Request TTS speech for response (Sentence level)
            websocket.send_json({
                "type": "tts_sentence",
                "sentence": "Enclosed space entry requires a valid permit.",
                "chunk_index": 0,
                "is_last": True
            })

            # 7. Receive tts_audio_chunk
            chunk_msg = websocket.receive_json()
            assert chunk_msg["type"] == "tts_audio_chunk"
            assert chunk_msg["audio"], "Audio chunk should contain base64 audio"

            # 8. Receive tts_completed
            comp_msg = websocket.receive_json()
            assert comp_msg["type"] == "tts_completed"

            # 9. Send playback_finished
            websocket.send_json({"type": "playback_finished"})
            listen_msg = websocket.receive_json()
            assert listen_msg["type"] == "listening"
            assert listen_msg["state"] == "LISTENING"

            # 10. Send session_end
            websocket.send_json({"type": "session_end"})
            end_msg = websocket.receive_json()
            assert end_msg["type"] == "session_ended"
