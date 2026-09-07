import asyncio
import sys
import io

import os
sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from api.dependencies import get_faiss_store, get_embedding_service, get_openai_service
from retrieval.retrieval_service import RetrievalService

async def test():
    store = get_faiss_store()
    openai_srv = get_openai_service()
    emb = get_embedding_service(openai_srv)
    rs = RetrievalService(store, emb)
    query = "centrifugal pump"
    chunks = await rs.search_similar(query, top_k=6)
    print(f"Retrieved {len(chunks)} chunks for query: '{query}'")
    for i, c in enumerate(chunks):
        title = c.get('title') or c.get('topic') or c.get('topic_name')
        course = c.get('course') or c.get('course_name')
        content = c.get('content') or c.get('topic_content') or c.get('text') or ''
        print(f"\n--- CHUNK {i+1}: Course: {course} | Topic: {title} ---")
        print(content[:600])

if __name__ == "__main__":
    asyncio.run(test())
