import sys
import asyncio
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pgdumplib
import asyncpg
import pendulum
from config import settings
from models.company_model import CompanyDocument
from retrieval.company_embedding import CompanyDocumentStore
from retrieval.faiss_store import FAISSStore

def parse_datetime(val):
    if not val:
        return datetime.utcnow()
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val)
    except Exception:
        try:
            return pendulum.parse(val)
        except Exception:
            return datetime.utcnow()

async def restore_company_docs():
    sql_path = Path(r"C:\Users\HP\Downloads\dolphin-db\dolphin-db.sql")
    if not sql_path.exists():
        print(f"Dump file not found at: {sql_path}")
        return
    
    print("Loading dump file using pgdumplib...")
    try:
        dump = pgdumplib.load(sql_path)
    except Exception as e:
        print(f"Failed to load dump file: {e}")
        return

    # Find company_documents table data entry
    doc_table_entry = None
    for entry in dump.entries:
        if entry.desc == "TABLE DATA" and entry.tag == "company_documents":
            doc_table_entry = entry
            break
            
    if not doc_table_entry:
        print("ERROR: company_documents table data entry not found in dump!")
        return
        
    print(f"Reading rows from '{doc_table_entry.tag}'...")
    rows = list(dump.table_data('public', 'company_documents'))
    print(f"Found {len(rows)} records in the dump for company_documents.")
    if not rows:
        print("No rows found. Exiting.")
        return
        
    # Connecting to remote Postgres database
    print(f"Connecting to Postgres at {settings.db_host}:{settings.db_port}...")
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        ssl=False,
        timeout=15
    )
    
    print("Connected to DB successfully.")
    
    # Insert or update rows in database
    insert_query = """
        INSERT INTO public.company_documents (
            document_id, company_id, document_title, document_content, content_type, is_active, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (document_id) DO UPDATE SET
            company_id = EXCLUDED.company_id,
            document_title = EXCLUDED.document_title,
            document_content = EXCLUDED.document_content,
            content_type = EXCLUDED.content_type,
            is_active = EXCLUDED.is_active,
            created_at = EXCLUDED.created_at,
            updated_at = EXCLUDED.updated_at
    """
    
    restored_docs = []
    print("Starting restore of database records...")
    async with conn.transaction():
        for r in rows:
            doc_id = int(r[0]) if r[0] is not None else None
            comp_id = str(r[1]) if r[1] is not None else ""
            title = str(r[2]) if r[2] is not None else ""
            content = str(r[3]) if r[3] is not None else ""
            content_type = str(r[4]) if r[4] is not None else "text/plain"
            is_active = (str(r[5]).lower() in ('true', 't', '1', 'yes')) if r[5] is not None else True
            created_at = parse_datetime(r[6])
            updated_at = parse_datetime(r[7])
            
            await conn.execute(
                insert_query,
                doc_id, comp_id, title, content, content_type, is_active, created_at, updated_at
            )
            
            content_length = len(content)
            
            restored_docs.append(CompanyDocument(
                document_id=doc_id,
                company_id=comp_id,
                document_title=title,
                document_content=content,
                content_length=content_length,
                is_active=is_active,
                created_at=created_at
            ))
            
    print(f"Successfully restored {len(restored_docs)} records to public.company_documents.")
    
    # Sync FAISS Index
    print("Preparing FAISS vector index rebuild...")
    
    # 1. Clean existing index files if they exist to prevent duplication
    index_path = Path("retrieval/company_index.bin")
    meta_path = Path("retrieval/company_index.meta.json")
    if index_path.exists():
        print(f"Removing old FAISS index file: {index_path}")
        index_path.unlink()
    if meta_path.exists():
        print(f"Removing old FAISS metadata file: {meta_path}")
        meta_path.unlink()
        
    # Group documents by company_id because we need to call add_documents for each company_id
    from collections import defaultdict
    docs_by_company = defaultdict(list)
    for doc in restored_docs:
        if doc.is_active:
            docs_by_company[doc.company_id].append(doc)
            
    # Initialize FAISSStore
    company_store = FAISSStore(
        index_path=str(index_path),
        meta_path=str(meta_path),
    )
    
    embedding_service = CompanyDocumentStore(company_store)
    
    for company_id, docs in docs_by_company.items():
        print(f"Generating embeddings and adding {len(docs)} documents to FAISS for company_id='{company_id}'...")
        await embedding_service.add_documents(company_id=company_id, documents=docs)
        
    print("FAISS vector store updated and saved successfully!")
    await conn.close()
    print("Database connection closed. Restore complete!")

if __name__ == "__main__":
    asyncio.run(restore_company_docs())
