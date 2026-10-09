import asyncio
import json
import time
import httpx

TEST_QUERIES = [
    "Explain the key differences between two-stroke and four-stroke marine diesel engines",
    "What are the requirements for lifeboats under SOLAS Chapter III?",
    "What are the duties of the Officer of the Watch (OOW) during navigation?",
]

async def test_all_queries():
    url = "http://127.0.0.1:8000/chat/working-stream"
    results = []

    for i, q in enumerate(TEST_QUERIES, 1):
        print(f"\n[{i}/{len(TEST_QUERIES)}] Testing query: '{q}'...")
        payload = {
            "content": q,
            "user_id": f"test_bench_{i}",
            "role": "Chief Engineer" if "diesel" in q else "Chief Officer",
            "company": "1",
        }

        t0 = time.perf_counter()
        first_token_time = None
        event_counts = {}
        content_tokens = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("POST", url, json=payload) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            raw_data = line[6:].strip()
                            try:
                                event = json.loads(raw_data)
                                etype = event.get("type", "unknown")
                                event_counts[etype] = event_counts.get(etype, 0) + 1

                                if etype == "content":
                                    token = event.get("token", "")
                                    content_tokens.append(token)
                                    if first_token_time is None and token.strip():
                                        first_token_time = time.perf_counter() - t0
                            except Exception:
                                pass

            total_time = time.perf_counter() - t0
            passed = total_time < 10.0
            full_text = "".join(content_tokens)
            results.append((q, total_time, first_token_time, passed, len(full_text)))

            print(f"  Time to first token: {first_token_time:.2f}s" if first_token_time else "  No tokens")
            print(f"  Total Stream Time: {total_time:.2f}s | Status: {'PASSED' if passed else 'FAILED'}")
            print(f"  Events: {event_counts}")
            print(f"  Response length: {len(full_text)} chars")

        except Exception as e:
            print(f"  Error: {e}")

    print("\n==========================================")
    print("BENCHMARK SUMMARY (< 10.0s target):")
    print("==========================================")
    for q, total, first_tok, passed, length in results:
        status_str = "PASSED" if passed else "FAILED"
        print(f"[{status_str}] {total:.2f}s (first token: {first_tok:.2f}s) - {q[:50]}...")

    all_passed = all(r[3] for r in results)
    print(f"\nOVERALL RESULT: {'ALL PASSED (< 10s)' if all_passed else 'SOME FAILED'}")

if __name__ == "__main__":
    asyncio.run(test_all_queries())
