"""
Video Transcript FAISS Index Builder
====================================
Builds `transcribe_index.bin` and `transcribe_index.meta.json` from PostgreSQL
(`public.transcribe` and `public.course_content.topic_video`).

Features:
- 3-Tier Deduplication (by Video ID, Canonical URL, and Content Hash)
- Text chunking (1000 chars, 200 overlap)
- OpenAI true batch embeddings (dim=3072, text-embedding-3-large)
- Crash-safe atomic write (.tmp -> final file)
- CLI args: --limit, --batch-size, --dry-run (inspect duplicates without spending API tokens)
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import faiss
import numpy as np
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

# Add parent directory to sys.path so backend imports work cleanly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")
load_dotenv(backend_dir.parent / ".env")

from models.database import get_pool
from retrieval.faiss_store import TRANSCRIBE_INDEX_PATH, TRANSCRIBE_META_PATH
from services.embedding_config import (
    BATCH_DELAY,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIM,
)
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService


def clean_html(text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    if not text:
        return ""
    if "<" not in text:
        return " ".join(text.split()).strip()

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
        soup = BeautifulSoup(text, "html.parser")
        return " ".join(soup.get_text(separator=" ").split()).strip()


def normalize_video_url(url: str) -> str:
    """Normalize video URL to catch duplicates across varying protocols/params."""
    if not url:
        return ""
    clean = url.strip().lower()
    clean = clean.split("?")[0].split("#")[0]
    clean = re.sub(r"^https?://", "", clean)
    clean = re.sub(r"/+", "/", clean).rstrip("/")
    return clean


async def fetch_video_items_from_db(
    limit: Optional[int] = None,
    existing_meta: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Fetch video rows from public.transcribe and public.course_content.
    Applies 3-tier deduplication by video_id, canonical URL, and text hash.
    If existing_meta is provided, pre-populates dedup sets to skip already vectorized videos.
    """
    pool = await get_pool()
    unique_items: List[Dict[str, Any]] = []
    seen_video_ids: Set[str] = set()
    seen_urls: Set[str] = set()
    seen_hashes: Set[str] = set()

    if existing_meta:
        logger.info("Loading {} existing metadata entries to skip already vectorized videos...", len(existing_meta))
        for m in existing_meta:
            v_id = str(m.get("video_id") or "").strip().lower()
            if v_id:
                seen_video_ids.add(v_id)
            v_url = normalize_video_url(m.get("video_link") or "")
            if v_url:
                seen_urls.add(v_url)
            c_txt = str(m.get("content") or "").strip()
            if c_txt:
                seen_hashes.add(hashlib.md5(c_txt[:250].encode("utf-8")).hexdigest())
        logger.info(
            "   - Pre-populated {} unique video IDs, {} URLs from existing FAISS index",
            len(seen_video_ids),
            len(seen_urls),
        )

    stats = {
        "transcribe_rows_read": 0,
        "course_content_videos_read": 0,
        "duplicate_video_ids": 0,
        "duplicate_urls": 0,
        "duplicate_content_hashes": 0,
        "empty_transcripts_skipped": 0,
        "total_unique_kept": 0,
    }

    logger.info("📡 Connecting to PostgreSQL to extract video transcripts...")

    # 1. Fetch from public.transcribe
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT video_id, video_title, video_link, video_thumbnail, video_duration,
                       topic_code, course_code, transcription_content
                FROM public.transcribe
                WHERE transcription_content IS NOT NULL
                  AND trim(transcription_content) != ''
                ORDER BY transcribe_id ASC
                """
            )
            stats["transcribe_rows_read"] = len(rows)
            logger.info("Found {} rows in public.transcribe", len(rows))

            for r in rows:
                raw_text = clean_html(str(r.get("transcription_content") or ""))
                if len(raw_text) < 25:
                    stats["empty_transcripts_skipped"] += 1
                    continue

                raw_url = str(r.get("video_link") or "").strip()
                v_id = str(r.get("video_id") or "").strip()
                norm_url = normalize_video_url(raw_url)

                # Dedup check
                v_id_clean = v_id.lower() if v_id else ""
                if v_id_clean and v_id_clean in seen_video_ids:
                    stats["duplicate_video_ids"] += 1
                    continue
                if norm_url and norm_url in seen_urls:
                    stats["duplicate_urls"] += 1
                    continue

                content_hash = hashlib.md5(raw_text[:250].encode("utf-8")).hexdigest()
                if content_hash in seen_hashes:
                    stats["duplicate_content_hashes"] += 1
                    continue

                if v_id_clean:
                    seen_video_ids.add(v_id_clean)
                if norm_url:
                    seen_urls.add(norm_url)
                seen_hashes.add(content_hash)

                fallback_id = v_id or (norm_url.split("/")[-1].replace(".mp4", "") if norm_url else f"vid_{len(unique_items)+1}")

                unique_items.append({
                    "video_id": fallback_id,
                    "video_title": str(r.get("video_title") or "Course Video").strip(),
                    "video_link": raw_url,
                    "video_thumbnail": str(r.get("video_thumbnail") or "").strip(),
                    "video_duration": str(r.get("video_duration") or "").strip(),
                    "topic_code": str(r.get("topic_code") or "").strip(),
                    "course_code": str(r.get("course_code") or "").strip(),
                    "transcript_text": raw_text,
                    "source_origin": "public.transcribe",
                })

                if limit and len(unique_items) >= limit:
                    break

    except Exception as e:
        logger.warning(f"Note: public.transcribe query issue (continuing with course_content): {e}")

    # 2. Fetch from course_content.topic_video if limit not yet reached
    if not limit or len(unique_items) < limit:
        try:
            async with pool.acquire() as conn:
                last_content_id = 0
                page_size = 5000
                logger.info("Scanning course_content in fast pages of {} rows...", page_size)

                while True:
                    if limit and len(unique_items) >= limit:
                        break

                    cc_rows = await conn.fetch(
                        """
                        SELECT content_id, course_code, topic_code, topic_name, topic_video
                        FROM public.course_content
                        WHERE content_id > $1
                        ORDER BY content_id ASC
                        LIMIT $2
                        """,
                        last_content_id, page_size
                    )
                    if not cc_rows:
                        break

                    last_content_id = cc_rows[-1]["content_id"]

                    for row in cc_rows:
                        if limit and len(unique_items) >= limit:
                            break

                        raw_vids = row.get("topic_video")
                        if not raw_vids:
                            continue

                        t_code = str(row.get("topic_code") or "").strip()
                        c_code = str(row.get("course_code") or "").strip()
                        t_name = str(row.get("topic_name") or "").strip()

                        if isinstance(raw_vids, str):
                            try:
                                raw_vids = json.loads(raw_vids)
                            except Exception:
                                raw_vids = []

                        if not isinstance(raw_vids, list):
                            continue

                        for v in raw_vids:
                            if not isinstance(v, dict):
                                continue
                            stats["course_content_videos_read"] += 1

                            raw_url = str(v.get("Url") or v.get("url") or v.get("videourl") or "").strip()
                            raw_id = str(v.get("Id") or v.get("id") or "").strip()
                            raw_id_clean = raw_id.lower() if raw_id else ""
                            raw_about = clean_html(str(v.get("About") or v.get("Caption") or v.get("about") or ""))

                            if len(raw_about) < 25:
                                stats["empty_transcripts_skipped"] += 1
                                continue

                            norm_url = normalize_video_url(raw_url)

                            if raw_id_clean and raw_id_clean in seen_video_ids:
                                stats["duplicate_video_ids"] += 1
                                continue
                            if norm_url and norm_url in seen_urls:
                                stats["duplicate_urls"] += 1
                                continue

                            content_hash = hashlib.md5(raw_about[:250].encode("utf-8")).hexdigest()
                            if content_hash in seen_hashes:
                                stats["duplicate_content_hashes"] += 1
                                continue

                            if raw_id_clean:
                                seen_video_ids.add(raw_id_clean)
                            if norm_url:
                                seen_urls.add(norm_url)
                            seen_hashes.add(content_hash)

                            fallback_id = raw_id or (norm_url.split("/")[-1].replace(".mp4", "") if norm_url else f"vid_{len(unique_items)+1}")
                            v_title = str(v.get("Title") or v.get("title") or t_name or "Course Video").strip()

                            unique_items.append({
                                "video_id": fallback_id,
                                "video_title": v_title,
                                "video_link": raw_url,
                                "video_thumbnail": str(v.get("Thumbnail") or v.get("thumbnail") or "").strip(),
                                "video_duration": str(v.get("Duration") or v.get("duration") or "").strip(),
                                "topic_code": t_code,
                                "course_code": c_code,
                                "transcript_text": raw_about,
                                "source_origin": "public.course_content",
                            })

                            if limit and len(unique_items) >= limit:
                                break

                    logger.info("   ... scanned up to content_id {}, unique videos kept: {}", last_content_id, len(unique_items))

        except Exception as e:
            logger.warning(f"course_content video reading error: {e}")

    stats["total_unique_kept"] = len(unique_items)
    return unique_items, stats


async def build_index(
    limit: Optional[int] = None,
    batch_size: int = EMBEDDING_BATCH_SIZE,
    dry_run: bool = False,
    rebuild: bool = False,
) -> None:
    """Main execution function."""
    t_start = time.perf_counter()
    logger.info("=" * 70)
    logger.info("🚀 STARTING VIDEO TRANSCRIBE FAISS INDEX BUILD")
    logger.info("   Target Output Index:    {}", TRANSCRIBE_INDEX_PATH)
    logger.info("   Target Output Metadata: {}", TRANSCRIBE_META_PATH)
    logger.info("   Embedding Model:        text-embedding-3-large (dim={})", EMBEDDING_DIM)
    if limit:
        logger.info("   Batch Limit:            {} video(s)", limit)
    if dry_run:
        logger.info("   Mode:                   DRY RUN (no OpenAI API calls)")

    existing_index = None
    existing_meta: List[Dict[str, Any]] = []
    has_existing = os.path.exists(TRANSCRIBE_INDEX_PATH) and os.path.exists(TRANSCRIBE_META_PATH)

    if has_existing and not rebuild:
        logger.info("🔄 Mode:                   INCREMENTAL (Preserve existing vectors + append new)")
        logger.info("   Loading existing FAISS: {}", TRANSCRIBE_INDEX_PATH)
        existing_index = faiss.read_index(TRANSCRIBE_INDEX_PATH)
        with open(TRANSCRIBE_META_PATH, "r", encoding="utf-8") as f:
            existing_meta = json.load(f)
        logger.info("   Existing Vectors:       {}, Existing Meta Items: {}", existing_index.ntotal, len(existing_meta))
    else:
        logger.info("🆕 Mode:                   FULL REBUILD (from scratch)")
    logger.info("=" * 70)

    # 1. Fetch & Deduplicate
    video_items, stats = await fetch_video_items_from_db(
        limit=limit,
        existing_meta=existing_meta if existing_index is not None else None,
    )

    logger.info("📊 Deduplication Summary:")
    logger.info("   - Transcribe rows read:     {}", stats["transcribe_rows_read"])
    logger.info("   - Course content videos:    {}", stats["course_content_videos_read"])
    logger.info("   - Skipped duplicate IDs:    {}", stats["duplicate_video_ids"])
    logger.info("   - Skipped duplicate URLs:   {}", stats["duplicate_urls"])
    logger.info("   - Skipped duplicate texts:  {}", stats["duplicate_content_hashes"])
    logger.info("   - Skipped empty transcripts:{}", stats["empty_transcripts_skipped"])
    logger.info("   - ✅ Total NEW videos:      {}", stats["total_unique_kept"])

    if not video_items:
        logger.success("✅ All videos are already vectorized in FAISS! Index is 100% up to date.")
        return

    # 2. Chunking
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    all_chunks: List[str] = []
    all_metadata: List[Dict[str, Any]] = []

    for v in video_items:
        chunks = splitter.split_text(v["transcript_text"])
        for idx, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_metadata.append({
                "source": "video_transcript",
                "course_code": v["course_code"],
                "topic_code": v["topic_code"],
                "video_id": v["video_id"],
                "video_link": v["video_link"],
                "video_title": v["video_title"],
                "video_duration": v["video_duration"],
                "video_thumbnail": v["video_thumbnail"],
                "chunk_index": idx,
                "content": chunk,
            })

    logger.info(
        "📝 Chunking complete: {} new video(s) -> {} searchable chunk(s) (~{:.1f} chunks/video)",
        len(video_items),
        len(all_chunks),
        len(all_chunks) / max(1, len(video_items)),
    )

    if dry_run:
        logger.success(
            "✅ Dry Run Finished! Processed {} new videos into {} chunks without calling OpenAI.",
            len(video_items),
            len(all_chunks),
        )
        return

    # 3. Generate Vector Embeddings via OpenAI
    logger.info("⚡ Generating OpenAI embeddings in batches of {}...", batch_size)
    openai_service = OpenAIService()
    embedder = EmbeddingService(openai_service)

    all_embeddings: List[List[float]] = []
    total_batches = (len(all_chunks) + batch_size - 1) // batch_size

    for b_idx in range(total_batches):
        start = b_idx * batch_size
        end = min(start + batch_size, len(all_chunks))
        batch_texts = all_chunks[start:end]

        t_batch_start = time.perf_counter()
        retries = 3
        batch_vectors = None

        for attempt in range(1, retries + 1):
            try:
                batch_vectors = await embedder.embed_documents(batch_texts)
                break
            except Exception as e:
                logger.warning(
                    "⚠️ Batch {}/{} failed (attempt {}/{}): {}",
                    b_idx + 1, total_batches, attempt, retries, e
                )
                if attempt < retries:
                    await asyncio.sleep(2.0 * attempt)
                else:
                    logger.error("❌ Batch {} failed permanently. Aborting build.", b_idx + 1)
                    raise

        if not batch_vectors or len(batch_vectors) != len(batch_texts):
            raise RuntimeError(f"Embedding count mismatch in batch {b_idx + 1}")

        all_embeddings.extend(batch_vectors)
        elapsed = time.perf_counter() - t_batch_start
        logger.info(
            "   [Batch {}/{}] Embedded {} chunks in {:.2f}s (Progress: {:.1f}%)",
            b_idx + 1,
            total_batches,
            len(batch_texts),
            elapsed,
            (len(all_embeddings) / len(all_chunks)) * 100.0,
        )

        if b_idx < total_batches - 1 and BATCH_DELAY > 0:
            await asyncio.sleep(BATCH_DELAY)

    # 4. Construct or Append FAISS Index (IndexFlatL2)
    embeddings_np = np.array(all_embeddings, dtype="float32")
    if embeddings_np.shape[1] != EMBEDDING_DIM:
        raise ValueError(f"Vector dim mismatch: expected {EMBEDDING_DIM}, got {embeddings_np.shape[1]}")

    if existing_index is not None:
        logger.info(
            "📦 Appending {} new vectors to existing FAISS index (previous count: {})...",
            len(all_embeddings),
            existing_index.ntotal,
        )
        index = existing_index
        index.add(embeddings_np)
        final_metadata = existing_meta + all_metadata
        logger.info("   -> Combined FAISS index count: {}", index.ntotal)
    else:
        logger.info("📦 Constructing new FAISS IndexFlatL2 with {} vectors (dim={})...", len(all_embeddings), EMBEDDING_DIM)
        index = faiss.IndexFlatL2(EMBEDDING_DIM)
        index.add(embeddings_np)
        final_metadata = all_metadata

    # 5. Atomic Safe Persistence (.tmp -> final file)
    tmp_index_path = f"{TRANSCRIBE_INDEX_PATH}.tmp"
    tmp_meta_path = f"{TRANSCRIBE_META_PATH}.tmp"

    logger.info("💾 Writing temporary files...")
    faiss.write_index(index, tmp_index_path)
    with open(tmp_meta_path, "w", encoding="utf-8") as f:
        json.dump(final_metadata, f, ensure_ascii=False, indent=2)

    # Atomically replace files
    if os.path.exists(TRANSCRIBE_INDEX_PATH):
        backup_path = f"{TRANSCRIBE_INDEX_PATH}.bak"
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.rename(TRANSCRIBE_INDEX_PATH, backup_path)

    os.rename(tmp_index_path, TRANSCRIBE_INDEX_PATH)

    if os.path.exists(TRANSCRIBE_META_PATH):
        backup_meta = f"{TRANSCRIBE_META_PATH}.bak"
        if os.path.exists(backup_meta):
            os.remove(backup_meta)
        os.rename(TRANSCRIBE_META_PATH, backup_meta)

    os.rename(tmp_meta_path, TRANSCRIBE_META_PATH)

    total_time = time.perf_counter() - t_start
    bin_size_mb = os.path.getsize(TRANSCRIBE_INDEX_PATH) / (1024 * 1024)
    meta_size_mb = os.path.getsize(TRANSCRIBE_META_PATH) / (1024 * 1024)

    logger.success("=" * 70)
    logger.success("🎉 TRANSCRIBE FAISS INDEX SUCCESSFULLY UPDATED!")
    logger.success("   Index file:     {} ({:.2f} MB)", TRANSCRIBE_INDEX_PATH, bin_size_mb)
    logger.success("   Metadata file:  {} ({:.2f} MB)", TRANSCRIBE_META_PATH, meta_size_mb)
    logger.success("   Total Vectors:  {}", index.ntotal)
    logger.success("   Total Time:     {:.2f}s", total_time)
    logger.success("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Build/Update FAISS vector index for video transcripts")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of unique new videos to process (e.g. --limit 50)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=EMBEDDING_BATCH_SIZE,
        help=f"OpenAI embedding batch size (default: {EMBEDDING_BATCH_SIZE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform database reading, deduplication, and chunking without calling OpenAI API",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        default=False,
        help="Wipe and rebuild entire index from scratch (default: False, runs incremental update)",
    )
    parser.add_argument("--db-host", type=str, default=None, help="PostgreSQL host (overrides config/env)")
    parser.add_argument("--db-port", type=int, default=None, help="PostgreSQL port (overrides config/env)")
    parser.add_argument("--db-name", type=str, default=None, help="PostgreSQL database name (overrides config/env)")
    parser.add_argument("--db-user", type=str, default=None, help="PostgreSQL user (overrides config/env)")
    parser.add_argument("--db-password", type=str, default=None, help="PostgreSQL password (overrides config/env)")
    args = parser.parse_args()

    from config import settings
    if args.db_host:
        settings.db_host = args.db_host
    if args.db_port:
        settings.db_port = args.db_port
    if args.db_name:
        settings.db_name = args.db_name
    if args.db_user:
        settings.db_user = args.db_user
    if args.db_password:
        settings.db_password = args.db_password

    logger.info("Database Target: {}@{}:{}/{}", settings.db_user, settings.db_host, settings.db_port, settings.db_name)

    asyncio.run(
        build_index(
            limit=args.limit,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            rebuild=args.rebuild,
        )
    )


if __name__ == "__main__":
    main()

