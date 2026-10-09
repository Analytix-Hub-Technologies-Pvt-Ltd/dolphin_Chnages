import asyncio
import json
import time
from services.openai_service import OpenAIService

TEST_PROMPT = """You are Marine Tutor AI answering marine education questions.

USER PROFILE:
Name: Test User
Role: Chief Officer
Ship: Tanker
Ship_type: Oil Tanker
Company: Marine Corp

CURRENT USER QUESTION:
What are the duties of the Officer of the Watch (OOW) during navigation?

COURSE CONTEXT:
TOPIC CODE: OOW-001
TOPIC NAME: Navigation Watchkeeping and OOW Duties
CONTENT:
The Officer of the Watch (OOW) is the Master's representative and is primarily responsible at all times for the safe navigation of the ship and compliance with the International Regulations for Preventing Collisions at Sea (COLREGS).
Key duties include:
1. Maintaining a continuous and proper lookout by sight and hearing as well as by all available means (radar, ARPA, AIS, ECDIS).
2. Monitoring the ship's position, course, and speed at frequent intervals using electronic and visual fixing methods.
3. Complying with passage plan directives, wheelhouse orders, and standing instructions from the Master.
4. Monitoring VHF radio communications and listening on Channel 16.
5. Inspecting navigation lights, shapes, and bridge equipment regularly.
6. Calling the Master immediately in cases of restricted visibility, heavy traffic, failure of bridge equipment, difficulty maintaining course, or any emergency.

RESPONSE FORMAT:
Return ONLY valid JSON.
{
  "sections": [
    {
      "topic_code": "OOW-001",
      "topic_name": "Navigation Watchkeeping and OOW Duties",
      "content": "### Navigation Watchkeeping and OOW Duties\\n\\nDetailed content here..."
    }
  ],
  "suggestions": [
    "Relevant follow-up question 1?",
    "Relevant follow-up question 2?",
    "Relevant follow-up question 3?"
  ]
}
"""

async def compare_models():
    service = OpenAIService()

    for model_name in ["gpt-4o-mini", "gpt-4o"]:
        print(f"\n--- Testing model: {model_name} ---")
        t0 = time.perf_counter()
        res = await service.chat(
            [{"role": "user", "content": TEST_PROMPT}],
            temperature=0.0,
            model=model_name,
            max_tokens=1500,
            response_format={"type": "json_object"}
        )
        elapsed = time.perf_counter() - t0
        print(f"Elapsed Time: {elapsed:.2f} seconds")
        try:
            parsed = json.loads(res)
            print("Valid JSON:", bool(parsed))
            sections = parsed.get("sections", [])
            print(f"Sections count: {len(sections)}")
            if sections:
                print("Content preview:", sections[0].get("content", "")[:200])
            print("Suggestions:", parsed.get("suggestions", []))
        except Exception as e:
            print("JSON parse error:", e)

if __name__ == "__main__":
    asyncio.run(compare_models())
