import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()

async def run():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "dalphin_db")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "root")
    
    conn = await asyncpg.connect(
        host=host,
        port=int(port),
        database=name,
        user=user,
        password=password,
        timeout=10
    )
    
    rows = await conn.fetch("SELECT document_id, document_title, document_content FROM company_documents")
    for r in rows:
        title = r["document_title"]
        content = r["document_content"] or ""
        content_lower = content.lower()
        if "crude oil" in content_lower or "cow" in content_lower:
            print(f"Match found in document: {title}")
            # print count of occurrences
            print(f"  'crude oil' count: {content_lower.count('crude oil')}")
            print(f"  'cow' count: {content_lower.count('cow')}")
            print(f"  'washing' count: {content_lower.count('washing')}")
            
    await conn.close()

if __name__ == "__main__":
    asyncio.run(run())
