import asyncio
from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app

def test_api():
    print("Initializing FastAPI TestClient...")
    client = TestClient(app)
    
    print("Testing GET /sessions?user_id=test-user...")
    try:
        response = client.get("/sessions", params={"user_id": "test-user"})
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Request failed with: {e}")

if __name__ == "__main__":
    test_api()
