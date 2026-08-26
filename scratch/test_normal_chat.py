import requests
import json

def test_chat():
    url = "http://127.0.0.1:8001/chat"
    payload = {
        "content": "hi",
        "user_id": "test-user-normal"
    }
    
    print("Testing standard chat endpoint on port 8001...")
    try:
        response = requests.post(url, json=payload, stream=True)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("Streaming chat response started:")
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        data = json.loads(decoded[6:])
                        print(data)
            print("\nChat stream complete.")
        else:
            print("Failed:")
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chat()
