import json
import base64
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from starlette.testclient import TestClient
from api.voice_router import router as voice_router
from models.node_response import NodeResponse
from services.tts_service import PiperTTSService


def test_voice_router_websocket_full_turn():
    # Build minimal FastAPI app containing only the voice router
    test_app = FastAPI()
    test_app.include_router(voice_router)

    tts_service = PiperTTSService.get_instance()
    wav_bytes = tts_service._synthesize_sentence_sync("What is enclosed space entry?")

    mock_node_response = NodeResponse(
        content="Enclosed space entry requires a valid entry permit, continuous atmospheric ventilation, and calibrated gas testing.",
        sections=[{"topic_code": "ESE_01", "topic_name": "Enclosed Space Entry"}],
        question_suggestions=["What PPE is required?"],
        metadata={"category": "QUERY"}
    )

    mock_pool = MagicMock()

    with patch("api.voice_router.get_pool", new_callable=AsyncMock) as mock_get_pool, \
         patch("api.voice_router.ChatService.run_chat", new_callable=AsyncMock) as mock_run_chat, \
         patch("api.voice_router.redis_service.get_active_session", new_callable=AsyncMock) as mock_get_sess, \
         patch("api.voice_router.redis_service.get_user_details", new_callable=AsyncMock) as mock_get_user, \
         patch("api.voice_router.redis_service.get_session_messages", new_callable=AsyncMock) as mock_get_msgs, \
         patch("api.voice_router.redis_service.set_session_messages", new_callable=AsyncMock), \
         patch("api.voice_router.SessionService.update_session_messages", new_callable=AsyncMock):

        mock_get_pool.return_value = mock_pool
        mock_get_sess.return_value = "test-user"
        mock_get_user.return_value = {"role": "Chief Officer"}
        mock_get_msgs.return_value = []
        mock_run_chat.return_value = (
            mock_node_response,
            [{"role": "user", "content": "What is enclosed space entry?"}, {"role": "assistant", "content": mock_node_response.content}],
            "What is enclosed space entry?",
            "Summary",
            {"videos": [], "images": []}
        )

        client = TestClient(test_app)
        with client.websocket_connect("/ws/voice/test-voice-session-001") as websocket:
            # 1. Receive session_started
            init_data = websocket.receive_json()
            assert init_data["type"] == "session_started"
            assert init_data["state"] == "LISTENING"

            # 2. Send audio chunk (base64 WAV)
            b64_audio = base64.b64encode(wav_bytes).decode("utf-8")
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

            # 6. Receive assistant_text (full visual response)
            asst_msg = websocket.receive_json()
            assert asst_msg["type"] == "assistant_text"
            assert "Enclosed space entry requires" in asst_msg["content"]

            # 7. Receive tts_started
            tts_start_msg = websocket.receive_json()
            assert tts_start_msg["type"] == "tts_started"
            assert tts_start_msg["total_sentences"] > 0

            # 8. Receive tts_audio_chunk
            chunk_msg = websocket.receive_json()
            assert chunk_msg["type"] == "tts_audio_chunk"
            assert chunk_msg["audio"], "Audio chunk should contain base64 WAV"

            # 9. Receive tts_completed
            tts_comp_msg = websocket.receive_json()
            assert tts_comp_msg["type"] == "tts_completed"
            assert tts_comp_msg["state"] == "LISTENING"

            # 10. Send session_end
            websocket.send_json({"type": "session_end"})
            end_msg = websocket.receive_json()
            assert end_msg["type"] == "session_ended"
