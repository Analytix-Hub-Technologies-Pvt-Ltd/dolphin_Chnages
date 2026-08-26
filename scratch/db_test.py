import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

async def test_db():
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    
    print(f"Connecting to Postgres at {host}:{port}/{name}...")
    
    try:
        conn = await asyncpg.connect(
            host=host,
            port=int(port),
            database=name,
            user=user,
            password=password,
            timeout=10
        )
        print("Connected.")
        
        print("\n--- Active Queries & Locks ---")
        query = """
        SELECT 
            pid, 
            state, 
            query_start, 
            now() - query_start AS duration, 
            query 
        FROM pg_stat_activity 
        WHERE state != 'idle' AND query NOT LIKE '%pg_stat_activity%';
        """
        rows = await conn.fetch(query)
        if not rows:
            print("No active (non-idle) queries found.")
        for r in rows:
            print(f"PID: {r['pid']} | State: {r['state']} | Duration: {r['duration']} | Query: {r['query'][:200]}")
            
        await conn.close()
    except Exception as e:
        print(f"FAILED with error: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())
