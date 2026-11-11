#!/usr/bin/env python3
"""
scripts/run_video_transcribe_client.py
======================================
Video Transcribe Extraction & FAISS Vector Index Builder for Client Database.

Performs:
1. Verifies/creates `public.transcribe` table on target PostgreSQL database.
2. Extracts video metadata & narrative 'About' text from `course_content.topic_video`.
3. Populates `public.transcribe` with cleaned transcripts.
4. Generates OpenAI text-embedding-3-large embeddings (dim=3072).
5. Persists FAISS IndexFlatL2 (`transcribe_index.bin` & `transcribe_index.meta.json`).

Usage:
    # 1. Populate transcribe table only (0 OpenAI tokens spent):
    python backend/scripts/run_video_transcribe_client.py --populate-table-only

    # 2. Dry run - inspect DB video count and chunk estimates:
    python backend/scripts/run_video_transcribe_client.py --dry-run

    # 3. Full run (extract + populate DB + vectorize):
    python backend/scripts/run_video_transcribe_client.py

    # 4. Limit for testing (e.g. 50 videos):
    python backend/scripts/run_video_transcribe_client.py --limit 50
"""

import os
import sys
import re
import json
import time
import argparse
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from dotenv import load_dotenv

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Load environment
load_dotenv(BACKEND_DIR / ".env")

# Default Client DB credentials
DEFAULT_CLIENT_DB = {
    "host": "192.168.2.75",
    "port": 5433,
    "dbname": "dolphin_ingestion",
    "user": "postgres",
    "password": "5BPXsrDXPS38Qt0v"
}

TRANSCRIBE_INDEX_PATH = str(BACKEND_DIR / "retrieval" / "transcribe_index.bin")
TRANSCRIBE_META_PATH = str(BACKEND_DIR / "retrieval" / "transcribe_index.meta.json")

def clean_html(text: str) -> str:
    """Fast regex HTML stripper and whitespace normalizer."""
    if not text:
        return ""
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", text)
    # Unescape common HTML entities
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return " ".join(clean.split()).strip()

def normalize_video_url(url: str) -> str:
    if not url:
        return ""
    clean = url.strip().lower()
    clean = clean.split("?")[0].split("#")[0]
    clean = re.sub(r"^https?://", "", clean)
    clean = re.sub(r"/+", "/", clean).rstrip("/")
    return clean

def ensure_transcribe_table(conn):
    """Ensure public.transcribe table and indexes exist on the target database."""
    print("Checking/creating public.transcribe table...", flush=True)
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.transcribe (
                transcribe_id BIGSERIAL PRIMARY KEY,
                course_code text,
                topic_code text,
                video_id text UNIQUE,
                video_link text,
                video_title text,
                video_duration text,
                video_thumbnail text,
                transcription_content text,
                status text,
                error_message text,
                created_at timestamp with time zone DEFAULT now() NOT NULL,
                updated_at timestamp with time zone DEFAULT now() NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_transcribe_video_id ON public.transcribe(video_id);
            CREATE INDEX IF NOT EXISTS idx_transcribe_topic_code ON public.transcribe(topic_code);
            CREATE INDEX IF NOT EXISTS idx_transcribe_course_code ON public.transcribe(course_code);
        """)
    conn.commit()
    print("  [OK] public.transcribe table and indexes verified.", flush=True)

def populate_transcribe_from_course_content(conn, limit: Optional[int] = None, db_params: Optional[dict] = None) -> int:
    """Extract videos from course_content.topic_video using streaming cursor and insert into public.transcribe."""
    print("\n--- EXTRACTING VIDEOS FROM course_content.topic_video ---", flush=True)
    
    # We use a separate dedicated connection for inserting while conn streams
    conn_insert = psycopg2.connect(**db_params) if db_params else psycopg2.connect(
        host=conn.info.host, port=conn.info.port, dbname=conn.info.dbname,
        user=conn.info.user, password=conn.info.password
    )
    cur_insert = conn_insert.cursor()

    query = """
        SELECT course_code, topic_code, topic_name, topic_video
        FROM course_content
        WHERE topic_video IS NOT NULL
          AND topic_video::text NOT IN ('', '[]', 'null', '{}')
        ORDER BY content_id ASC;
    """
    
    cur_stream = conn.cursor(name='video_stream_cursor', cursor_factory=RealDictCursor)
    cur_stream.itersize = 500
    cur_stream.execute(query)

    videos_batch = []
    seen_vids = set()
    skipped_empty = 0
    total_upserted = 0
    batch_size = 500

    def _flush_batch(batch):
        nonlocal total_upserted
        if not batch:
            return
        execute_values(
            cur_insert,
            """
            INSERT INTO public.transcribe (
                course_code, topic_code, video_id, video_link,
                video_title, video_duration, video_thumbnail,
                transcription_content, status
            ) VALUES %s
            ON CONFLICT (video_id) DO UPDATE SET
                course_code = EXCLUDED.course_code,
                topic_code = EXCLUDED.topic_code,
                video_link = EXCLUDED.video_link,
                video_title = EXCLUDED.video_title,
                video_duration = EXCLUDED.video_duration,
                video_thumbnail = EXCLUDED.video_thumbnail,
                transcription_content = EXCLUDED.transcription_content,
                status = EXCLUDED.status,
                updated_at = now();
            """,
            batch
        )
        conn_insert.commit()
        total_upserted += len(batch)
        sys.stdout.write(f"\r  Extracted & Saved {total_upserted:,} unique videos to public.transcribe...   ")
        sys.stdout.flush()

    for r in cur_stream:
        c_code = str(r['course_code'] or '').strip()
        t_code = str(r['topic_code'] or '').strip()
        vids = r['topic_video']
        if isinstance(vids, str):
            try:
                vids = json.loads(vids)
            except Exception:
                vids = []
        if not isinstance(vids, list):
            continue

        for v in vids:
            if not isinstance(v, dict):
                continue
            vid_id = str(v.get('Id') or v.get('id') or '').strip()
            if not vid_id:
                continue
            if vid_id in seen_vids:
                continue
            seen_vids.add(vid_id)

            raw_about = str(v.get('About') or v.get('about') or v.get('Caption') or '').strip()
            clean_text = clean_html(raw_about)

            if len(clean_text) < 15:
                skipped_empty += 1
                clean_text = None

            v_url = str(v.get('Url') or v.get('url') or v.get('VideoUrl') or '').strip()
            v_title = str(v.get('Title') or v.get('title') or r['topic_name'] or 'Course Video').strip()
            v_dur = str(v.get('Duration') or v.get('duration') or '').strip()
            v_thumb = str(v.get('Thumbnail') or v.get('thumbnail') or '').strip()

            videos_batch.append((
                c_code,
                t_code,
                vid_id,
                v_url,
                v_title,
                v_dur,
                v_thumb,
                clean_text,
                "completed" if clean_text else "no_transcript"
            ))

            if len(videos_batch) >= batch_size:
                _flush_batch(videos_batch)
                videos_batch = []

            if limit and (total_upserted + len(videos_batch)) >= limit:
                break
        if limit and (total_upserted + len(videos_batch)) >= limit:
            break

    if videos_batch:
        _flush_batch(videos_batch)

    cur_stream.close()
    conn.commit()
    cur_insert.close()
    conn_insert.close()

    print(f"\n  [OK] Done! Successfully populated {total_upserted:,} videos in public.transcribe (Skipped empty text: {skipped_empty:,}).", flush=True)
    return total_upserted

def build_faiss_transcribe_index(conn, limit: Optional[int] = None, dry_run: bool = False, batch_size: int = 100):
    """Build FAISS vector index for video transcripts using OpenAI text-embedding-3-large."""
    print("\n--- PREPARING FAISS VECTORIZATION ---", flush=True)
    import faiss
    import numpy as np
    from openai import OpenAI

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT video_id, video_title, video_link, video_thumbnail, video_duration,
                   topic_code, course_code, transcription_content
            FROM public.transcribe
            WHERE transcription_content IS NOT NULL
              AND LENGTH(TRIM(transcription_content)) > 20
            ORDER BY transcribe_id ASC;
        """)
        rows = cur.fetchall()

    if limit:
        rows = rows[:limit]

    print(f"Found {len(rows):,} videos with valid transcript content.", flush=True)

    # Chunking: split text into ~1000 char chunks with 200 char overlap
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    chunks = []
    chunk_meta = []
    seen_hashes = set()

    for r in rows:
        text = r['transcription_content']
        v_chunks = text_splitter.split_text(text)
        for idx, ch in enumerate(v_chunks):
            ch_clean = ch.strip()
            if len(ch_clean) < 20:
                continue
            h = hashlib.md5(ch_clean.encode('utf-8')).hexdigest()
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            chunks.append(ch_clean)
            chunk_meta.append({
                "source": "video_transcript",
                "course_code": r['course_code'],
                "topic_code": r['topic_code'],
                "video_id": r['video_id'],
                "video_link": r['video_link'],
                "video_title": r['video_title'],
                "video_duration": r['video_duration'],
                "video_thumbnail": r['video_thumbnail'],
                "chunk_index": idx,
                "content": ch_clean
            })

    print(f"Total transcript chunks to vectorize: {len(chunks):,}", flush=True)

    if dry_run:
        print(f"\n[DRY RUN] Would generate embeddings for {len(chunks):,} chunks.")
        print(f"Estimated OpenAI Tokens: ~{len(chunks) * 200:,}")
        print("Dry run complete. No FAISS index modified.")
        return

    # OpenAI API Client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in environment or backend/.env!", flush=True)
        return

    client = OpenAI(api_key=api_key)
    model = "text-embedding-3-large"
    dim = 3072

    print(f"\nGenerating embeddings using OpenAI '{model}' (dim={dim})...", flush=True)
    all_embeddings = []
    t0 = time.time()

    for i in range(0, len(chunks), batch_size):
        batch_text = chunks[i:i + batch_size]
        # Call OpenAI
        resp = client.embeddings.create(input=batch_text, model=model)
        batch_embs = [d.embedding for d in resp.data]
        all_embeddings.extend(batch_embs)

        pct = int((len(all_embeddings) / len(chunks)) * 100)
        sys.stdout.write(f"\r  Embedded {len(all_embeddings):,} / {len(chunks):,} chunks ({pct}%)...   ")
        sys.stdout.flush()

    print(f"\n  [OK] Generated {len(all_embeddings):,} embeddings in {time.time()-t0:.2f}s.", flush=True)

    # Build FAISS IndexFlatL2
    print("Building FAISS IndexFlatL2...", flush=True)
    embeddings_np = np.array(all_embeddings, dtype=np.float32)
    faiss.normalize_L2(embeddings_np)
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings_np)

    # Save to disk with backup
    tmp_bin = TRANSCRIBE_INDEX_PATH + ".tmp"
    tmp_meta = TRANSCRIBE_META_PATH + ".tmp"

    faiss.write_index(index, tmp_bin)
    with open(tmp_meta, 'w', encoding='utf-8') as f:
        json.dump(chunk_meta, f, indent=2, ensure_ascii=False)

    if os.path.exists(TRANSCRIBE_INDEX_PATH):
        bak = TRANSCRIBE_INDEX_PATH + ".bak"
        if os.path.exists(bak): os.remove(bak)
        os.rename(TRANSCRIBE_INDEX_PATH, bak)
    os.rename(tmp_bin, TRANSCRIBE_INDEX_PATH)

    if os.path.exists(TRANSCRIBE_META_PATH):
        bak_m = TRANSCRIBE_META_PATH + ".bak"
        if os.path.exists(bak_m): os.remove(bak_m)
        os.rename(TRANSCRIBE_META_PATH, bak_m)
    os.rename(tmp_meta, TRANSCRIBE_META_PATH)

    print("=" * 80)
    print("SUCCESS: Video Transcribe FAISS Index updated!")
    print(f"  Index file:    {TRANSCRIBE_INDEX_PATH} ({os.path.getsize(TRANSCRIBE_INDEX_PATH)/(1024*1024):.2f} MB)")
    print(f"  Metadata file: {TRANSCRIBE_META_PATH} ({os.path.getsize(TRANSCRIBE_META_PATH)/(1024*1024):.2f} MB)")
    print(f"  Total Vectors: {index.ntotal:,}")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Run Video Transcribe Extraction & Vectorization for Client DB")
    parser.add_argument("--host", default=DEFAULT_CLIENT_DB["host"])
    parser.add_argument("--port", type=int, default=DEFAULT_CLIENT_DB["port"])
    parser.add_argument("--dbname", default=DEFAULT_CLIENT_DB["dbname"])
    parser.add_argument("--user", default=DEFAULT_CLIENT_DB["user"])
    parser.add_argument("--password", default=DEFAULT_CLIENT_DB["password"])
    parser.add_argument("--populate-table-only", action="store_true", help="Only extract & insert videos into public.transcribe (no OpenAI vectorization)")
    parser.add_argument("--vectorize-only", action="store_true", help="Skip extraction and build FAISS from existing public.transcribe")
    parser.add_argument("--dry-run", action="store_true", help="Estimate chunk counts without calling OpenAI API")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of videos to process")
    parser.add_argument("--batch-size", type=int, default=100, help="Embedding batch size (default 100)")
    args = parser.parse_args()

    print("=" * 80)
    print(f"VIDEO TRANSCRIBE RUNNER | Target DB: {args.user}@{args.host}:{args.port}/{args.dbname}")
    print("=" * 80, flush=True)

    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=args.password,
        connect_timeout=15
    )

    db_params = {
        "host": args.host,
        "port": args.port,
        "dbname": args.dbname,
        "user": args.user,
        "password": args.password,
    }

    try:
        ensure_transcribe_table(conn)

        if not args.vectorize_only:
            populate_transcribe_from_course_content(conn, limit=args.limit, db_params=db_params)

        if not args.populate_table_only:
            build_faiss_transcribe_index(conn, limit=args.limit, dry_run=args.dry_run, batch_size=args.batch_size)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
