import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from models.database import get_pool

async def run():
    pool = await get_pool()
    conn = await pool.acquire()
    try:
        for days in [1, 7, 30, 45, 60, 90, 180, 365]:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM course_content WHERE fetched_on >= CURRENT_DATE - INTERVAL '{days} days'")
            print(f"Last {days} days: {count} rows")
        total = await conn.fetchval("SELECT COUNT(*) FROM course_content")
        print(f"Total rows in DB: {total}")
    finally:
        await conn.close()
        await pool.close()

if __name__ == "__main__":
    asyncio.run(run())
