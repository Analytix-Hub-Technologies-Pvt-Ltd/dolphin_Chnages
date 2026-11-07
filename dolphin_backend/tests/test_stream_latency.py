import asyncio
import json
import time
import httpx

async def test_stream():
    url = "http://127.0.0.1:8000/chat/working-stream"
    payload = {
        "content": "What is the procedure for enclosed space entry on a ship?",
        "user_id": "test_user_stream",
        "role": "Chief Officer",
        "company": "1",
    }

    print(f"Connecting to {url}...")
    t0 = time.perf_counter()
    first_token_time = None
    event_counts = {}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                print(f"Status Code: {response.status_code}")
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        raw_data = line[6:].strip()
                        try:
                            event = json.loads(raw_data)
                            etype = event.get("type", "unknown")
                            event_counts[etype] = event_counts.get(etype, 0) + 1

                            if etype == "content" and first_token_time is None:
                                first_token_time = time.perf_counter() - t0
                                print(f"⏱️ First content token arrived in: {first_token_time:.2f}s")
                        except Exception:
                            pass

        total_time = time.perf_counter() - t0
        print(f"\n==========================================")
        print(f"TOTAL SSE STREAM TIME: {total_time:.2f} seconds")
        print(f"Event summary: {event_counts}")
        print(f"Target < 10.0s: {'PASSED' if total_time < 10.0 else 'FAILED'}")
        print(f"==========================================")

    except Exception as e:
        import traceback
        print(f"Error testing stream: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_stream())
