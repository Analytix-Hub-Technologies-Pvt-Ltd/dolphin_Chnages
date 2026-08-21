import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import asyncpg
import time
from config import settings

async def test_pool():
    print(f"Creating pool to {settings.db_host}:{settings.db_port}...")
    start = time.time()
    try:
        pool = await asyncpg.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            min_size=2,
            max_size=20,
            command_timeout=60,
            timeout=30,
        )
        print(f"Pool created successfully in {time.time() - start:.2f} seconds!")
        
        async with pool.acquire() as conn:
            row_count = await conn.fetchval("SELECT COUNT(*) FROM course_content")
            print(f"Row count: {row_count}")
            
        await pool.close()
    except Exception as e:
        print(f"Pool creation/query FAILED after {time.time() - start:.2f} seconds: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_pool())
