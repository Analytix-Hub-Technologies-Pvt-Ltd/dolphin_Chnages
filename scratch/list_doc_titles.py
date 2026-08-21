import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import asyncpg
from config import settings

async def list_titles():
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
        rows = await conn.fetch(
            "SELECT document_id, company_id, document_title, char_length(document_content) as content_length, is_active FROM public.company_documents"
        )
        print(f"Total documents: {len(rows)}")
        for r in rows:
            print(f"ID: {r['document_id']} | Company: {r['company_id']} | Title: {r['document_title']} | Length: {r['content_length']} chars | Active: {r['is_active']}")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_titles())
