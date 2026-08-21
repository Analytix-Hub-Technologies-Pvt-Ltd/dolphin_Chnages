import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import asyncpg
from config import settings

async def check_tables():
    print(f"Connecting to {settings.db_host}:{settings.db_port}...")
    try:
        conn = await asyncpg.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            ssl=False,
            timeout=10
        )
        print("Connected!")
        tables = ['chat_sessions', 'course_content', 'master_course_data', 'open_ai_log', 'tutor_content', 'users', 'company_documents', 'transcribe']
        for table in tables:
            try:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM public.{table}")
                print(f"Table public.{table}: {count} rows")
            except Exception as e:
                print(f"Table public.{table}: Error: {e}")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_tables())
