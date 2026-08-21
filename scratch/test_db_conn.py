import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import asyncpg
from config import settings

async def test_conn():
    print(f"Connecting to {settings.db_host}:{settings.db_port} as {settings.db_user}...")
    
    # Test 1: Without SSL parameters (default)
    try:
        print("Test 1: Default SSL settings...")
        conn = await asyncpg.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            timeout=10
        )
        print("Test 1 SUCCESS!")
        await conn.close()
    except Exception as e:
        print(f"Test 1 FAILED: {type(e).__name__}: {e}")

    # Test 2: With ssl='require' (or ssl=True)
    try:
        print("\nTest 2: ssl='require'...")
        conn = await asyncpg.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            ssl='require',
            timeout=10
        )
        print("Test 2 SUCCESS!")
        await conn.close()
    except Exception as e:
        print(f"Test 2 FAILED: {type(e).__name__}: {e}")

    # Test 3: With ssl=False
    try:
        print("\nTest 3: ssl=False...")
        conn = await asyncpg.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            ssl=False,
            timeout=10
        )
        print("Test 3 SUCCESS!")
        await conn.close()
    except Exception as e:
        print(f"Test 3 FAILED: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_conn())
