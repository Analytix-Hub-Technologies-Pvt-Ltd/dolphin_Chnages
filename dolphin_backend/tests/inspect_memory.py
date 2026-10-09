import asyncio
import json
from models.database import get_pool

async def main():
    pool = await get_pool()
    fb_rows = await pool.fetch("SELECT feedback_id, question, status, edited_response, original_response, created_at, updated_at FROM public.feedback ORDER BY feedback_id DESC LIMIT 5")
    for r in fb_rows:
        print("=== FEEDBACK ===")
        print("ID:", r["feedback_id"])
        print("Question:", repr(r["question"]))
        print("Status:", r["status"])
        print("Edited Response:", repr((r["edited_response"] or "")[:200]))
        print("Original Response:", repr((r["original_response"] or "")[:200]))
    
    mem_rows = await pool.fetch("SELECT memory_id, feedback_id, question, preferred_response, is_active, updated_at FROM public.approved_feedback_memory ORDER BY updated_at DESC LIMIT 5")
    for m in mem_rows:
        print("=== MEMORY ===")
        print("Memory ID:", m["memory_id"])
        print("Feedback ID:", m["feedback_id"])
        print("Question:", repr(m["question"]))
        print("Preferred Response:", repr((m["preferred_response"] or "")[:200]))
        print("Is Active:", m["is_active"])

if __name__ == "__main__":
    asyncio.run(main())
