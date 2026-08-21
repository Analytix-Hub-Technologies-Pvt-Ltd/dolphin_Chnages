import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from models.database import get_pool

async def run():
    pool = await get_pool()
    conn = await pool.acquire()
    try:
        rows = await conn.fetch('SELECT DISTINCT fetched_on::date FROM course_content ORDER BY fetched_on::date DESC LIMIT 15')
        print("Latest fetched dates:")
        for r in rows:
            print(f"  {r['fetched_on']}")
    finally:
        await conn.close()
        await pool.close()

if __name__ == "__main__":
    asyncio.run(run())
