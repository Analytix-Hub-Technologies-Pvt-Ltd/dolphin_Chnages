import asyncio
from models.database import get_pool

async def main():
    pool = await get_pool()
    rows = await pool.fetch("SELECT feedback_id, question, original_response, edited_response, reviewer_notes, status, created_at, updated_at FROM public.feedback ORDER BY feedback_id DESC LIMIT 10")
    for r in rows:
        print(f"=== Feedback ID {r['feedback_id']} (status: {r['status']}) ===")
        print(f"Question: {r['question']}")
        print(f"Original: {(r['original_response'] or '')[:120]}")
        print(f"Edited:   {(r['edited_response'] or '')[:120]}")
        print(f"Notes:    {r['reviewer_notes']}")
        print(f"Updated:  {r['updated_at']}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
