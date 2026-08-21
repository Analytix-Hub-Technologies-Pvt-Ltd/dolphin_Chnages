import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from models.database import get_pool

async def run():
    pool = await get_pool()
    conn = await pool.acquire()
    try:
        row = await conn.fetchrow("SELECT * FROM users LIMIT 1")
        if row:
            print("Columns in users table:")
            for k in row.keys():
                print(f"  {k}: {row[k]}")
        else:
            print("Users table is empty!")
    finally:
        await conn.close()
        await pool.close()

if __name__ == "__main__":
    asyncio.run(run())
