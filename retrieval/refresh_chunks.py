from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
import sys

import numpy as np
from loguru import logger
from tqdm.auto import tqdm
from apscheduler.triggers.cron import CronTrigger

from models.database import get_pool
from retrieval.faiss_store import FAISSStore
from services.openai_service import OpenAIService
from services.embedding_service import EmbeddingService
from services.embedding_config import (
    EMBEDDING_DIM,
    EMBEDDING_BATCH_SIZE,
    CHECKPOINT_INTERVAL,
    BATCH_DELAY
)


async def _fetch_course_rows_batch(
    days: Optional[int] = None,
    limit: int = 1000,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Fetch a batch of rows from course_content table using LIMIT/OFFSET.
    This prevents loading all rows into memory at once.
    
    Args:
        days: If specified, only fetch rows from the last N days.
        limit: Number of rows to fetch in this batch.
        offset: Starting position for this batch.
    
    Returns:
        List of row dictionaries for this batch.
    """
    pool = await get_pool()
    
    if days is not None:
        # Use string formatting for INTERVAL since it's a type modifier, not a value
        sql = f"""
            SELECT
                content_id,
                course_code,
                topic_code,
                topic_name,
                topic_video,
                topic_image,
                topic_pdf,
                topic_content,
                fetched_on
            FROM course_content
            WHERE fetched_on >= CURRENT_DATE - INTERVAL '{days} days'
            ORDER BY content_id
            LIMIT $1 OFFSET $2
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, limit, offset)
            logger.debug(sql)
    else:
        sql = """
            SELECT
                content_id,
                course_code,
                topic_code,
                topic_name,
                topic_video,
                topic_image,
                topic_pdf,
                topic_content,
                fetched_on
            FROM course_content
            ORDER BY content_id
            LIMIT $1 OFFSET $2
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, limit, offset)
            logger.debug(sql)

    course_rows = [dict(r) for r in rows]
    return course_rows


async def _fetch_course_rows(days: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Load rows from the canonical course_content table.
    DEPRECATED: This loads all rows at once. Use batch processing instead.
    
    Args:
        days: If specified, only fetch rows from the last N days.
              If None, fetch all rows.
    """
    pool = await get_pool()
    
    if days is not None:
        sql = f"""
            SELECT
                content_id,
                course_code,
                topic_code,
                topic_name,
                topic_video,
                topic_image,
                topic_pdf,
                topic_content,
                fetched_on
            FROM course_content
            WHERE fetched_on >= CURRENT_DATE - INTERVAL '{days} days'
            ORDER BY content_id
        """
        logger.info("Fetching course_content from last {} days...", days)
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql)
    else:
        sql = """
            SELECT
                content_id,
                course_code,
                topic_code,
                topic_name,
                topic_video,
                topic_image,
                topic_pdf,
                topic_content,
                fetched_on
            FROM course_content
            ORDER BY content_id
        """
        logger.info("Fetching ALL course_content rows...")
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql)

    course_rows = [dict(r) for r in rows]
    logger.info("course_content rows fetched: {}", len(course_rows))
    return course_rows


async def _get_row_count(days: Optional[int] = None) -> int:
    """Get total count of rows to process."""
    pool = await get_pool()
    
    if days is not None:
        # Use f-string for INTERVAL since it's a type modifier, not a value
        sql = f"""
            SELECT COUNT(*) as count
            FROM course_content
            WHERE fetched_on >= CURRENT_DATE - INTERVAL '{days} days'
        """
        async with pool.acquire() as conn:
            result = await conn.fetchrow(sql)
    else:
        sql = "SELECT COUNT(*) as count FROM course_content"
        async with pool.acquire() as conn:
            result = await conn.fetchrow(sql)
    
    return result['count'] if result else 0


async def _generate_embeddings_batch(
    texts: List[str],
    embedder: EmbeddingService,
    batch_size: int = 100,
    max_retries: int = 3,
    delay_between_batches: float = 1.0
) -> List[List[float]]:
    """
    Generate embeddings in TRUE batches with rate limiting and retry logic.
    Uses OpenAI's batch embedding API for massive speed improvements.
    
    Args:
        texts: List of texts to embed
        embedder: EmbeddingService instance
        batch_size: Number of texts to process per batch (OpenAI allows up to 2048)
        max_retries: Number of retry attempts for failed batches
        delay_between_batches: Seconds to wait between batches (rate limiting)
    """
    all_embeddings: List[List[float]] = []
    total_batches = (len(texts) + batch_size - 1) // batch_size
    
    logger.info(
        f"Generating embeddings for {len(texts)} texts in {total_batches} batches "
        f"(batch_size={batch_size}) using TRUE batch API"
    )
    
    for batch_idx in tqdm(range(0, len(texts), batch_size), desc="Embedding batches"):
        batch_texts = texts[batch_idx:batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1
        
        for attempt in range(max_retries):
            try:
                # Use TRUE batch embedding - single API call for all texts in batch
                logger.debug(f"Batch {batch_num}/{total_batches}: Processing {len(batch_texts)} texts in one API call")
                batch_embeddings = await embedder.embed_documents(batch_texts)
                
                # Validate all embeddings
                for i, vec in enumerate(batch_embeddings):
                    if len(vec) != EMBEDDING_DIM:
                        raise ValueError(
                            f"Embedding dimension mismatch at index {i}. "
                            f"Expected {EMBEDDING_DIM}, got {len(vec)}"
                        )
                
                all_embeddings.extend(batch_embeddings)
                logger.debug(f"Batch {batch_num}/{total_batches}: Successfully generated {len(batch_embeddings)} embeddings")
                
                # Rate limiting delay between batches
                if batch_idx + batch_size < len(texts):
                    await asyncio.sleep(delay_between_batches)
                
                break  # Success, exit retry loop
                
            except Exception as e:
                logger.warning(
                    f"Batch {batch_num}/{total_batches} failed "
                    f"(attempt {attempt + 1}/{max_retries}): {str(e)}"
                )
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"Batch {batch_num} failed after "
                        f"{max_retries} attempts. Aborting."
                    )
                    raise
    
    logger.info(f"Successfully generated {len(all_embeddings)} embeddings")
    return all_embeddings


async def rebuild_faiss_index(
    store: FAISSStore,
    days: Optional[int] = None,
    batch_size: int = EMBEDDING_BATCH_SIZE,
    checkpoint_interval: int = CHECKPOINT_INTERVAL
) -> None:
    """
    Full rebuild from course_content → embeddings → FAISS index.
    Optimized for large datasets with TRUE batching and checkpointing.

    - Reads course_content rows (all or last N days)
    - Builds chunks using topic_name + topic_content (no media chunking)
    - Calls OpenAI embeddings in TRUE batches via EmbeddingService
    - Builds FAISS index + metadata with checkpointing every N rows
    - Saves to disk via FAISSStore.save()
    
    Args:
        store: FAISSStore instance
        days: If specified, only process rows from last N days. If None, process all.
        batch_size: Number of embeddings per API batch (increased to 500 for speed)
        checkpoint_interval: Save checkpoint every N rows (saves progress for huge datasets)
    """
    import pickle
    from pathlib import Path
    
    try:
        if days:
            logger.info("Rebuilding FAISS index from last {} days...", days)
        else:
            logger.info("Loading/Rebuilding FAISS index (startup/scheduled)...")

        # Get total count first
        total_count = await _get_row_count(days)
        logger.info(f"Total rows to process: {total_count}")
        
        if total_count == 0:
            logger.warning("No course_content rows found. FAISS index will be empty.")
            store.reset()
            store.is_loaded = True
            store.save()
            return

        # Init embedding stack
        openai_service = OpenAIService()
        embedder = EmbeddingService(openai_service)

        # Checkpoint setup
        checkpoint_dir = Path("data/checkpoints")
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_file = checkpoint_dir / "faiss_rebuild_checkpoint.pkl"
        
        # Check for existing checkpoint
        resume_from = 0
        all_embeddings: List[List[float]] = []
        all_metadatas: List[Dict[str, Any]] = []
        
        if checkpoint_file.exists():
            try:
                logger.info("Found existing checkpoint, attempting to resume...")
                with open(checkpoint_file, 'rb') as f:
                    checkpoint_data = pickle.load(f)
                    resume_from = checkpoint_data.get('processed_count', 0)
                    all_embeddings = checkpoint_data.get('embeddings', [])
                    all_metadatas = checkpoint_data.get('metadatas', [])
                    logger.info(f"Resuming from row {resume_from} with {len(all_embeddings)} existing embeddings")
            except Exception as e:
                logger.warning(f"Could not load checkpoint: {e}. Starting from scratch.")
                resume_from = 0
                all_embeddings = []
                all_metadatas = []

        # Process in batches - fetch from database in chunks to avoid loading all rows into memory
        logger.info(f"Processing {total_count} rows (starting from row {resume_from})...")
        logger.info("Using batch fetching from database to manage memory efficiently")
        
        # Calculate which database batch to start from
        db_batch_size = checkpoint_interval  # Fetch same size as checkpoint interval
        db_offset = (resume_from // db_batch_size) * db_batch_size
        
        processed_count = resume_from
        
        while processed_count < total_count:
            # Fetch next batch from database (not from memory!)
            logger.info(f"Fetching database batch: offset {db_offset}, limit {db_batch_size}...")
            chunk_rows = await _fetch_course_rows_batch(days=days, limit=db_batch_size, offset=db_offset)
            
            if not chunk_rows:
                logger.warning(f"No more rows fetched at offset {db_offset}. Stopping.")
                break
            
            # Calculate actual chunk boundaries within this batch
            # Skip rows that were already processed (if resuming mid-batch)
            skip_in_batch = processed_count - db_offset
            chunk_start_in_batch = skip_in_batch
            chunk_end_in_batch = min(chunk_start_in_batch + checkpoint_interval, len(chunk_rows))
            
            # Process this chunk
            chunk_start = processed_count
            chunk_end = processed_count + (chunk_end_in_batch - chunk_start_in_batch)
            actual_chunk_rows = chunk_rows[chunk_start_in_batch:chunk_end_in_batch]
            
            # Skip if no rows to process in this batch (already processed)
            if not actual_chunk_rows:
                db_offset += db_batch_size
                continue
            
            logger.info(f"Processing chunk {chunk_start} to {chunk_end} ({len(actual_chunk_rows)} rows)...")
            
            # Prepare texts and metadata for this chunk
            texts: List[str] = []
            metadatas: List[Dict[str, Any]] = []

            for row in tqdm(actual_chunk_rows, desc=f"Preparing chunk {chunk_start}-{chunk_end}"):
                topic_name = row.get("topic_name", "")
                topic_content = row.get("topic_content", "")
                combined_text = f"Topic Name: {topic_name}\n\nTopic Content:\n{topic_content}"

                texts.append(combined_text)
                metadatas.append(
                    {
                        "content_id": row.get("content_id"),
                        "topic_code": row.get("topic_code"),
                        "topic_name": row.get("topic_name"),
                        "topic_content": row.get("topic_content"),
                        "content": combined_text,
                    }
                )

            # Generate embeddings for this chunk in batches
            logger.info(f"Generating embeddings for chunk {chunk_start}-{chunk_end}...")
            chunk_embeddings = await _generate_embeddings_batch(
                texts=texts,
                embedder=embedder,
                batch_size=batch_size,
                max_retries=3,
                delay_between_batches=BATCH_DELAY  # From config for rate limiting
            )

            # Verify chunk embeddings
            if len(chunk_embeddings) != len(texts):
                raise ValueError(
                    f"Embedding count mismatch in chunk! Expected {len(texts)}, got {len(chunk_embeddings)}"
                )

            # Append to overall results
            all_embeddings.extend(chunk_embeddings)
            all_metadatas.extend(metadatas)
            
            # Save checkpoint after each chunk
            logger.info(f"Saving checkpoint at row {chunk_end}...")
            try:
                with open(checkpoint_file, 'wb') as f:
                    pickle.dump({
                        'processed_count': chunk_end,
                        'embeddings': all_embeddings,
                        'metadatas': all_metadatas,
                        'total_rows': total_count
                    }, f)
                logger.info(f"✓ Checkpoint saved: {len(all_embeddings)} embeddings processed")
            except Exception as e:
                logger.warning(f"Failed to save checkpoint: {e}")
            
            # Update counters for next iteration
            processed_count = chunk_end
            
            # If we've processed all rows in this database batch, move to next batch
            if chunk_end_in_batch >= len(chunk_rows):
                db_offset += db_batch_size
            
            # Memory management: log current progress
            logger.info(
                f"Progress: {len(all_embeddings)}/{total_count} embeddings "
                f"({len(all_embeddings)/total_count*100:.1f}%)"
            )

        logger.info(f"Completed embedding generation: {len(all_embeddings)} total embeddings")

        # Verify we got all embeddings
        if len(all_embeddings) != total_count:
            raise ValueError(
                f"Final embedding count mismatch! Expected {total_count}, got {len(all_embeddings)}"
            )

        # Convert to numpy array
        logger.info("Converting embeddings to numpy array...")
        emb_array = np.array(all_embeddings, dtype="float32")
        logger.info(
            "Embeddings array shape: {} (rows) x {} (dim)",
            emb_array.shape[0],
            emb_array.shape[1],
        )

        # Validate array is not empty
        if emb_array.size == 0:
            raise ValueError("Generated embeddings array is empty!")

        # Build + persist FAISS index
        logger.info("Building FAISS index...")
        store.build_from_embeddings(emb_array, all_metadatas)
        
        logger.info("Saving FAISS index to disk...")
        store.save()

        # Verify the save was successful
        index_path = Path(store.index_path)
        if not index_path.exists():
            raise RuntimeError(f"Index file was not created at {store.index_path}")
        
        file_size = index_path.stat().st_size
        if file_size == 0:
            raise RuntimeError("Index file is empty (0 bytes)!")
        
        logger.success(
            "FAISS rebuild COMPLETE - {} vectors loaded! File size: {:.2f} MB",
            emb_array.shape[0],
            file_size / (1024 * 1024)
        )
        
        # Clean up checkpoint file on success
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            logger.info("Checkpoint file cleaned up")

    except Exception as e:
        logger.error(f"FAISS rebuild FAILED: {str(e)}")
        logger.exception(e)
        logger.error("Checkpoint file preserved for resume. Run again to continue from last checkpoint.")
        raise


# ------------------------------------------------------------
# Scheduler helper
# ------------------------------------------------------------
def schedule_daily_rebuild(scheduler, store: FAISSStore) -> None:
    """
    Attach a daily 03:00 AM async FAISS rebuild job to the given AsyncIOScheduler.
    """

    async def _job():
        logger.info("Scheduler tick - starting nightly FAISS rebuild...")
        try:
            await rebuild_faiss_index(store)
        except Exception as e:
            logger.error(f"Scheduled FAISS rebuild failed: {str(e)}")
            logger.exception(e)

    # Wrap coroutine in a task so scheduler can call a normal function
    def _job_wrapper():
        asyncio.create_task(_job())

    scheduler.add_job(
        _job_wrapper,
        CronTrigger(hour=3, minute=0),
        id="faiss_daily_rebuild",
        replace_existing=True,
    )