import requests

def test_gap_check():
    url = "http://127.0.0.1:8000/companies/check-gaps"
    file_path = "tests/test_sms_document.txt"
    
    print("Testing gap check API endpoint...")
    with open(file_path, "rb") as f:
        files = {"file": (file_path.split("/")[-1], f, "text/plain")}
        try:
            response = requests.post(url, files=files)
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                print("Success! Gap analysis response:")
                data = response.json()
                print(data.get("gap_analysis")[:300] + "...")
            else:
                print("Failed:")
                print(response.text)
        except Exception as e:
            print(f"Error connecting to server: {e}")

if __name__ == "__main__":
    test_gap_check()
