import requests
import json

def test_stream():
    url = "http://127.0.0.1:8000/companies/check-gaps?stream=true"
    file_path = "tests/test_sms_document.txt"
    
    print("Testing streaming gap check API endpoint...")
    with open(file_path, "rb") as f:
        files = {"file": (file_path.split("/")[-1], f, "text/plain")}
        try:
            response = requests.post(url, files=files, stream=True)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print("Streaming response started:")
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data: "):
                            data = json.loads(decoded_line[6:])
                            # Safely encode/print to avoid console charmap errors
                            token = data.get("token", "")
                            print(token.encode('ascii', errors='replace').decode('ascii'), end="", flush=True)
                print("\nStream complete.")
            else:
                print("Failed:")
                print(response.text)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_stream()
