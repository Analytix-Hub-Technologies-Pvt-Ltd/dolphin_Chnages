import asyncio
import os
import sys
from dotenv import load_dotenv
import asyncpg

load_dotenv()

async def run():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "dalphin_db")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "root")
    
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
        
        # 1. Print all users
        print("\n--- Users Table ---")
        rows = await conn.fetch("SELECT * FROM users")
        for r in rows:
            print(dict(r))
            
        # 2. Print all company documents details
        print("\n--- Company Documents ---")
        docs = await conn.fetch("SELECT document_id, company_id, document_title FROM company_documents")
        for d in docs:
            print(dict(d))
            
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run())
