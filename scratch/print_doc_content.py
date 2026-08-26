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
    
    print("Connecting...")
    conn = await asyncpg.connect(
        host=host,
        port=int(port),
        database=name,
        user=user,
        password=password,
        timeout=10
    )
    
    # Query document content
    row = await conn.fetchrow(
        "SELECT document_content FROM company_documents WHERE document_title = $1 LIMIT 1",
        "Shipboard SMS Manual (OSV).docx"
    )
    if row:
        content = row["document_content"]
        with open("scratch/doc_content_cow.txt", "w", encoding="utf-8") as f:
            f.write(content)
        print("Written full document to scratch/doc_content_cow.txt.")
    else:
        print("Document not found in database.")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(run())
