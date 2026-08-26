import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

async def list_topics():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "dalphin_db")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "root")
    
    print(f"Connecting to {host}:{port}/{name}...")
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
        
        # Get unique course codes and topics
        query = "SELECT DISTINCT course_code, topic_code, topic_name FROM course_content ORDER BY course_code, topic_name;"
        rows = await conn.fetch(query)
        print(f"\nFound {len(rows)} topics in course_content:")
        for r in rows:
            print(f"- Course: {r['course_code']} | Code: {r['topic_code']} | Name: {r['topic_name']}")
            
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_topics())
