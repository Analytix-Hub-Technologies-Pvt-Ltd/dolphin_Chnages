import json
import os

import pytest

from services.embedding_config import EMBEDDING_DIM

requests = pytest.importorskip("requests")


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Requires running FastAPI server (uvicorn main:app) and Postgres",
)

def test_multiple_sessions():
    """Test that different sessions don't interfere with each other"""
    assert EMBEDDING_DIM == 3072
    base_url = "http://localhost:8000"
    user_id = "test-user-multi"

    print("🧪 Multiple Sessions Test")
    print("=" * 40)

    # Create two different sessions
    sessions = []
    for i in range(2):
        session_resp = requests.post(f"{base_url}/sessions", json={
            "user_id": user_id,
            "title": f"Session {i+1}"
        })
        session_id = session_resp.json()["session_id"]
        sessions.append(session_id)
        print(f"Created session {i+1}: {session_id}")

    # Send different messages to each session
    session_messages = {
        sessions[0]: ["What is marine propulsion?", "Tell me about diesel engines"],
        sessions[1]: ["What is ship navigation?", "Explain GPS systems"]
    }

    for session_id, messages in session_messages.items():
        print(f"\n💬 Testing session {session_id}:")
        for msg in messages:
            resp = requests.post(f"{base_url}/chat", json={
                "session_id": session_id,
                "message": msg
            })
            assert resp.status_code == 200, f"Chat failed: {resp.text}"
            print(f"   ✅ Sent: {msg}")

    # Verify sessions are isolated
    for i, session_id in enumerate(sessions):
        session_check = requests.get(f"{base_url}/sessions/{session_id}", params={"user_id": user_id})
        session_data = session_check.json()
        messages = session_data.get("messages", [])

        user_messages = [m for m in messages if m.get("role") == "user"]
        expected_messages = session_messages[session_id]

        print(f"\n📋 Session {i+1} messages:")
        for msg in user_messages:
            msg_text = str(msg.get("content", ""))
            print(f"   - {msg_text}")

        assert len(user_messages) == len(expected_messages), f"Session {i+1} has wrong message count"
        for msg in messages:
            assert isinstance(msg, dict)
            assert "role" in msg and "content" in msg and "category" in msg
            assert "question" not in msg and "response" not in msg
            assert msg != "[" and msg != "]"

    print("✅ SUCCESS: Sessions are properly isolated!")


if __name__ == "__main__":
    test_multiple_sessions()
