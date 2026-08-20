# tests/test_chat_endpoint_detailed.py
import json
import os

import pytest

requests = pytest.importorskip("requests")


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Requires running FastAPI server (uvicorn main:app) and Postgres",
)

def test_chat_endpoint_detailed():
    base_url = "http://localhost:8000"
    
    print("🔍 Detailed Chat Endpoint Analysis")
    print("=" * 45)
    
    # First create a session
    print("1. Creating session...")
    session_response = requests.post(f"{base_url}/sessions", json={
        "user_id": "chat-test-user",
        "title": "Chat Test Session"
    })
    
    if session_response.status_code != 200:
        print(f"❌ Session creation failed: {session_response.text}")
        return
        
    session_data = session_response.json()
    session_id = session_data["session_id"]
    print(f"✅ Session created: {session_id}")
    
    # Test chat endpoint with detailed error info
    print(f"\n2. Testing chat endpoint with session {session_id}...")
    
    chat_payload = {
        "session_id": session_id,
        "user_id": "chat-test-user",
        "message": "What is marine safety?"
    }
    
    try:
        response = requests.post(
            f"{base_url}/chat",
            json=chat_payload,
            timeout=30  # Longer timeout for chat processing
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            chat_data = response.json()
            print("✅ Chat successful!")
            print(f"   Response: {chat_data.get('response', '')[:100]}...")
            print(f"   Node type: {chat_data.get('node_type')}")
        else:
            print(f"   Response body: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - endpoint might not exist")
    except requests.exceptions.Timeout:
        print("❌ Request timeout - endpoint exists but processing is slow")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_chat_endpoint_detailed()