import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from models.database import get_pool

async def run():
    pool = await get_pool()
    if not pool:
        print("Could not create pool.")
        return
    conn = await pool.acquire()
    try:
        rows = await conn.fetch("SELECT email FROM users LIMIT 20")
        print("Emails in DB:")
        for r in rows:
            print(f"  {r['email']}")
    finally:
        await conn.close()
        await pool.close()

if __name__ == "__main__":
    asyncio.run(run())
