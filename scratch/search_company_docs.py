import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import asyncpg
from config import settings

async def search_docs(query_text: str):
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
        
        # Simple case-insensitive match on title or content
        # We can rank by whether the title contains it, or the frequency/presence in content
        query = """
            SELECT document_id, company_id, document_title, document_content
            FROM public.company_documents
            WHERE is_active = TRUE 
              AND (document_title ILIKE $1 OR document_content ILIKE $1)
            LIMIT 5
        """
        search_pattern = f"%{query_text}%"
        rows = await conn.fetch(query, search_pattern)
        
        if not rows:
            print("NO_RESULTS")
            await conn.close()
            return
            
        print(f"FOUND {len(rows)} DOCUMENTS\n")
        for r in rows:
            doc_id = r['document_id']
            company_id = r['company_id']
            title = r['document_title']
            content = r['document_content']
            
            print(f"=== DOCUMENT ID: {doc_id} | COMPANY ID: {company_id} | TITLE: {title} ===")
            
            # Extract relevant snippets around the query term
            idx = content.lower().find(query_text.lower())
            if idx != -1:
                start = max(0, idx - 400)
                end = min(len(content), idx + 800)
                snippet = content[start:end]
                print(f"[Snippet near match]:\n... {snippet} ...\n")
            else:
                print(f"[Content snippet (first 1000 chars)]:\n{content[:1000]}...\n")
                
        await conn.close()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search company documents in database")
    parser.add_argument("query", type=str, help="Search keyword or phrase")
    args = parser.parse_args()
    
    asyncio.run(search_docs(args.query))
