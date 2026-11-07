"""
selective_faiss_sync.py
======================
Incremental / Selective FAISS Vector Synchronization System for Dolphin.

KEY FEATURES:
1. Detects DB changes in PostgreSQL `course_content` at topic & course level.
2. Extracts and preserves unchanged vectors directly from existing FAISS index (0.2s, $0 cost).
3. Generates OpenAI embeddings ONLY for updated/new topics.
4. Updates FAISS IndexFlatL2 and metadata atomically with safety backups.
5. Emits a rich, easy-to-read JSON report ('faiss_sync_report.json') containing:
   - Exactly how much time each phase took (formatted as HH:MM:SS)
   - "Before Update" metrics vs "After Update" metrics
   - Detailed topic-level and course-level change log
   - Token usage and estimated cost

USAGE:
  # Check only (dry-run) - detects changes, estimates time & tokens without modifying index:
  python retrieval/selective_faiss_sync.py --dry-run

  # Run selective sync for changes since a specific date:
  python retrieval/selective_faiss_sync.py --since 2026-07-01

  # Run selective sync for a single course:
  python retrieval/selective_faiss_sync.py --course <course_code>

  # Run full scan across all courses (detects updated, added, and deleted topics):
  python retrieval/selective_faiss_sync.py
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import faiss
import numpy as np
from loguru import logger
from tqdm import tqdm

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings
from models.database import close_pool, get_pool
from services.embedding_config import EMBEDDING_BATCH_SIZE, EMBEDDING_DIM, EMBEDDING_MODEL
from services.embedding_service import EmbeddingService
from services.openai_service import OpenAIService

DEFAULT_INDEX_PATH = BACKEND_DIR / "retrieval" / "faiss_index.bin"
DEFAULT_META_PATH = BACKEND_DIR / "retrieval" / "faiss_index.meta.json"
REPORT_PATH = BACKEND_DIR / "retrieval" / "faiss_sync_report.json"
HISTORY_DIR = BACKEND_DIR / "retrieval" / "faiss_sync_history"


def format_seconds(seconds: float) -> str:
    """Format seconds into HH:MM:SS format."""
    total_sec = int(round(seconds))
    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    return f"{hrs:02d}h:{mins:02d}m:{secs:02d}s"


def compute_content_fingerprint(topic_name: str, topic_content: str) -> str:
    """Compute SHA-256 hash of combined topic text for exact change detection."""
    combined = f"Topic Name: {topic_name or ''}\n\nTopic Content:\n{topic_content or ''}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


class SelectiveFaissSyncService:
    def __init__(
        self,
        index_path: Path = DEFAULT_INDEX_PATH,
        meta_path: Path = DEFAULT_META_PATH,
        report_path: Path = REPORT_PATH,
        batch_size: int = EMBEDDING_BATCH_SIZE,
    ):
        self.index_path = Path(index_path)
        self.meta_path = Path(meta_path)
        self.report_path = Path(report_path)
        self.batch_size = batch_size

        self.openai_service: Optional[OpenAIService] = None
        self.embedder: Optional[EmbeddingService] = None

    def _init_embedder(self):
        if self.embedder is None:
            self.openai_service = OpenAIService()
            self.embedder = EmbeddingService(self.openai_service)

    def load_existing_faiss(self) -> Tuple[faiss.Index, List[Dict[str, Any]], Dict[str, Any]]:
        """Load current FAISS index and metadata sidecar, returning 'before' stats."""
        if not self.index_path.exists():
            raise FileNotFoundError(f"FAISS index binary not found at {self.index_path}")
        if not self.meta_path.exists():
            raise FileNotFoundError(f"FAISS metadata JSON not found at {self.meta_path}")

        t0 = time.time()
        logger.info(f"📦 Loading existing FAISS index from {self.index_path.name}...")
        index = faiss.read_index(str(self.index_path))

        logger.info(f"📄 Loading existing FAISS metadata from {self.meta_path.name}...")
        with open(self.meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        load_sec = time.time() - t0
        bin_size_mb = self.index_path.stat().st_size / (1024 * 1024)
        meta_size_mb = self.meta_path.stat().st_size / (1024 * 1024)

        courses = set()
        for m in metadata:
            c = m.get("course_code")
            if c:
                courses.add(c)

        before_stats = {
            "total_vectors": index.ntotal,
            "total_topics_in_meta": len(metadata),
            "distinct_courses_in_meta": len(courses),
            "index_file_size_mb": round(bin_size_mb, 2),
            "meta_file_size_mb": round(meta_size_mb, 2),
            "load_time_seconds": round(load_sec, 2),
        }

        logger.success(
            f"✅ Existing FAISS loaded: {index.ntotal:,} vectors, {len(metadata):,} metadata items "
            f"({bin_size_mb:.1f} MB index, {meta_size_mb:.1f} MB metadata) in {load_sec:.2f}s"
        )
        return index, metadata, before_stats

    async def fetch_db_candidates(
        self,
        since_date: Optional[str] = None,
        course_code: Optional[str] = None,
        days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query candidate rows from PostgreSQL `course_content`.
        Deduplicates rows by topic_code taking latest content_id.
        """
        pool = await get_pool()
        where_clauses = []
        params = []

        if course_code:
            params.append(course_code)
            where_clauses.append(f"course_code = ${len(params)}")

        if since_date:
            try:
                # Validate date
                d = datetime.date.fromisoformat(since_date)
                params.append(d)
                where_clauses.append(f"fetched_on >= ${len(params)}")
            except Exception as e:
                logger.error(f"Invalid since_date '{since_date}': {e}")
                raise

        if days is not None:
            where_clauses.append(f"fetched_on >= CURRENT_DATE - INTERVAL '{days} days'")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Deduplicate by topic_code taking max(content_id) to guard against any double ingestion
        sql = f"""
            SELECT DISTINCT ON (topic_code)
                content_id,
                course_code,
                topic_code,
                topic_name,
                topic_content,
                fetched_on
            FROM course_content
            {where_sql}
            ORDER BY topic_code, content_id DESC
        """

        logger.info(f"🔍 Fetching candidates from PostgreSQL `course_content` (filters: {where_clauses or 'ALL'})...")
        t0 = time.time()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
        fetch_sec = time.time() - t0

        logger.info(f"✓ Fetched {len(rows):,} distinct topic rows from PostgreSQL in {fetch_sec:.2f}s")
        return [dict(r) for r in rows]

    def analyze_changes(
        self,
        existing_metadata: List[Dict[str, Any]],
        db_rows: List[Dict[str, Any]],
        is_full_scan: bool = True,
    ) -> Dict[str, Any]:
        """
        Compare PostgreSQL rows with existing FAISS metadata.
        Returns categorized changes: UPDATED, NEW, DELETED, UNCHANGED.
        """
        t0 = time.time()

        # Build index maps for fast O(1) lookup
        # Map: topic_code -> (faiss_idx, meta_dict)
        meta_by_topic: Dict[str, Tuple[int, Dict[str, Any]]] = {}
        meta_by_cid: Dict[int, Tuple[int, Dict[str, Any]]] = {}

        for idx, m in enumerate(existing_metadata):
            t_code = m.get("topic_code")
            cid = m.get("content_id")
            if t_code:
                meta_by_topic[t_code] = (idx, m)
            if cid is not None:
                meta_by_cid[int(cid)] = (idx, m)

        updated_topics: List[Dict[str, Any]] = []
        new_topics: List[Dict[str, Any]] = []
        unchanged_indices: Set[int] = set()
        matched_faiss_indices: Set[int] = set()

        # Courses affected tracking
        affected_courses: Dict[str, Dict[str, int]] = {}

        def record_affected_course(c_code: str, action: str):
            c_code = c_code or "UNKNOWN_COURSE"
            if c_code not in affected_courses:
                affected_courses[c_code] = {"UPDATED": 0, "NEW": 0, "DELETED": 0}
            affected_courses[c_code][action] += 1

        for row in tqdm(db_rows, desc="Analyzing topic diffs"):
            t_code = row.get("topic_code")
            cid = row.get("content_id")
            c_code = row.get("course_code") or ""
            t_name = row.get("topic_name") or ""
            t_content = row.get("topic_content") or ""

            new_fingerprint = compute_content_fingerprint(t_name, t_content)

            # Check if topic exists in FAISS (by topic_code first, then by content_id)
            match = meta_by_topic.get(t_code) or (meta_by_cid.get(cid) if cid is not None else None)

            if match is not None:
                faiss_idx, old_meta = match
                matched_faiss_indices.add(faiss_idx)

                old_t_name = old_meta.get("topic_name") or ""
                old_t_content = old_meta.get("topic_content") or ""
                old_fingerprint = compute_content_fingerprint(old_t_name, old_t_content)

                if new_fingerprint != old_fingerprint:
                    # Content or title changed!
                    diff_item = {
                        "course_code": c_code,
                        "topic_code": t_code,
                        "topic_name": t_name,
                        "content_id": cid,
                        "faiss_index_pos": faiss_idx,
                        "action": "UPDATED",
                        "reason": "topic_content modified" if old_t_content != t_content else "topic_name modified",
                        "char_length_before": len(old_t_content),
                        "char_length_after": len(t_content),
                        "row_data": row,
                    }
                    updated_topics.append(diff_item)
                    record_affected_course(c_code, "UPDATED")
                else:
                    unchanged_indices.add(faiss_idx)
            else:
                # Brand new topic not present in FAISS
                diff_item = {
                    "course_code": c_code,
                    "topic_code": t_code,
                    "topic_name": t_name,
                    "content_id": cid,
                    "faiss_index_pos": None,
                    "action": "NEW",
                    "reason": "New topic discovered in DB",
                    "char_length_before": 0,
                    "char_length_after": len(t_content),
                    "row_data": row,
                }
                new_topics.append(diff_item)
                record_affected_course(c_code, "NEW")

        # In full scan mode, any FAISS entry that was NOT matched against DB is considered DELETED in DB
        deleted_topics: List[Dict[str, Any]] = []
        if is_full_scan:
            all_faiss_indices = set(range(len(existing_metadata)))
            unmatched = all_faiss_indices - matched_faiss_indices
            for idx in unmatched:
                m = existing_metadata[idx]
                c_code = m.get("course_code") or ""
                diff_item = {
                    "course_code": c_code,
                    "topic_code": m.get("topic_code"),
                    "topic_name": m.get("topic_name"),
                    "content_id": m.get("content_id"),
                    "faiss_index_pos": idx,
                    "action": "DELETED",
                    "reason": "Topic row no longer exists in DB",
                    "char_length_before": len(m.get("topic_content") or ""),
                    "char_length_after": 0,
                }
                deleted_topics.append(diff_item)
                record_affected_course(c_code, "DELETED")
        else:
            # If not a full scan, keep all existing indices that were not evaluated in candidate set
            all_faiss_indices = set(range(len(existing_metadata)))
            evaluated_indices = matched_faiss_indices
            unevaluated_indices = all_faiss_indices - evaluated_indices
            unchanged_indices.update(unevaluated_indices)

        diff_time = time.time() - t0

        return {
            "analysis_time_seconds": round(diff_time, 2),
            "updated_topics": updated_topics,
            "new_topics": new_topics,
            "deleted_topics": deleted_topics,
            "unchanged_indices": sorted(list(unchanged_indices)),
            "affected_courses": affected_courses,
            "total_to_embed": len(updated_topics) + len(new_topics),
        }

    async def generate_embeddings_for_diff(
        self,
        items_to_embed: List[Dict[str, Any]],
    ) -> Tuple[np.ndarray, float, int]:
        """
        Embed ONLY the updated and new topics using OpenAI text-embedding-3-large batch API.
        Returns: (vectors numpy array, duration_seconds, token_count)
        """
        if not items_to_embed:
            return np.empty((0, EMBEDDING_DIM), dtype="float32"), 0.0, 0

        self._init_embedder()
        t0 = time.time()

        texts = []
        for item in items_to_embed:
            row = item["row_data"]
            t_name = row.get("topic_name") or ""
            t_content = row.get("topic_content") or ""
            text = f"Topic Name: {t_name}\n\nTopic Content:\n{t_content}".strip()
            if not text:
                text = "marine topic"
            texts.append(text)

        logger.info(
            f"🚀 Calling OpenAI embedding API for {len(texts)} topics in batches of {self.batch_size}..."
        )

        all_vectors: List[List[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_vectors = await self.embedder.embed_documents(batch)
            all_vectors.extend(batch_vectors)

        duration = time.time() - t0
        arr = np.array(all_vectors, dtype="float32")

        # Rough token approximation: ~1 token per 4 characters
        approx_tokens = sum(len(t) // 4 for t in texts)

        logger.success(
            f"✅ Generated {arr.shape[0]} embeddings in {duration:.2f}s "
            f"(avg {duration / max(1, len(texts)):.3f}s per topic, ~{approx_tokens:,} tokens)"
        )
        return arr, duration, approx_tokens

    def execute_sync(
        self,
        current_index: faiss.Index,
        current_metadata: List[Dict[str, Any]],
        analysis: Dict[str, Any],
        new_embeddings: np.ndarray,
    ) -> Tuple[faiss.Index, List[Dict[str, Any]], Dict[str, Any]]:
        """
        Reconstruct unchanged vectors from current FAISS index, merge with new embeddings,
        and construct the updated FAISS IndexFlatL2 + metadata list.
        """
        t0 = time.time()
        unchanged_indices = analysis["unchanged_indices"]
        updated_topics = analysis["updated_topics"]
        new_topics = analysis["new_topics"]

        logger.info(f"🔄 Reconstructing {len(unchanged_indices):,} unchanged vectors from existing FAISS...")
        if unchanged_indices:
            # High-speed batch reconstruction
            unchanged_vecs = np.zeros((len(unchanged_indices), EMBEDDING_DIM), dtype="float32")
            for out_pos, orig_pos in enumerate(unchanged_indices):
                unchanged_vecs[out_pos] = current_index.reconstruct(orig_pos)
            unchanged_metadata = [current_metadata[idx] for idx in unchanged_indices]
        else:
            unchanged_vecs = np.empty((0, EMBEDDING_DIM), dtype="float32")
            unchanged_metadata = []

        # Prepare new and updated records
        new_meta_records: List[Dict[str, Any]] = []
        items_combined = updated_topics + new_topics

        for item in items_combined:
            row = item["row_data"]
            t_name = row.get("topic_name") or ""
            t_content = row.get("topic_content") or ""
            c_text = f"Topic Name: {t_name}\n\nTopic Content:\n{t_content}"
            new_meta_records.append(
                {
                    "content_id": row.get("content_id"),
                    "course_code": row.get("course_code"),
                    "topic_code": row.get("topic_code"),
                    "topic_name": t_name,
                    "topic_content": t_content,
                    "content": c_text,
                }
            )

        # Merge vectors: unchanged vectors + newly embedded vectors
        if new_embeddings.size > 0:
            final_vectors = np.vstack([unchanged_vecs, new_embeddings]).astype("float32")
        else:
            final_vectors = unchanged_vecs.astype("float32")

        final_metadata = unchanged_metadata + new_meta_records

        logger.info(f"🏗️ Building updated FAISS IndexFlatL2 ({final_vectors.shape[0]:,} vectors)...")
        new_index = faiss.IndexFlatL2(EMBEDDING_DIM)
        if final_vectors.shape[0] > 0:
            new_index.add(final_vectors)

        rebuild_time = time.time() - t0
        logger.success(f"✅ In-memory FAISS index updated in {rebuild_time:.2f}s")

        return new_index, final_metadata, {"rebuild_time_seconds": round(rebuild_time, 2)}

    def save_atomic_with_backup(
        self,
        new_index: faiss.Index,
        new_metadata: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Save updated FAISS index & metadata atomically with backup."""
        t0 = time.time()
        logger.info("💾 Creating backup of existing FAISS files...")

        backup_bin = self.index_path.with_suffix(".bin.bak")
        backup_meta = self.meta_path.with_suffix(".meta.json.bak")

        if self.index_path.exists():
            shutil.copy2(self.index_path, backup_bin)
        if self.meta_path.exists():
            shutil.copy2(self.meta_path, backup_meta)

        tmp_bin = self.index_path.with_suffix(".bin.tmp")
        tmp_meta = self.meta_path.with_suffix(".meta.json.tmp")

        logger.info(f"Writing {tmp_bin.name}...")
        faiss.write_index(new_index, str(tmp_bin))

        logger.info(f"Writing {tmp_meta.name}...")
        with open(tmp_meta, "w", encoding="utf-8") as f:
            json.dump(new_metadata, f, ensure_ascii=False)

        # Atomic replacement
        if self.index_path.exists():
            os.replace(tmp_bin, self.index_path)
        else:
            tmp_bin.rename(self.index_path)

        if self.meta_path.exists():
            os.replace(tmp_meta, self.meta_path)
        else:
            tmp_meta.rename(self.meta_path)

        save_time = time.time() - t0
        final_bin_mb = self.index_path.stat().st_size / (1024 * 1024)
        final_meta_mb = self.meta_path.stat().st_size / (1024 * 1024)

        logger.success(
            f"💾 Successfully saved updated FAISS files ({final_bin_mb:.1f} MB bin, "
            f"{final_meta_mb:.1f} MB meta) in {save_time:.2f}s"
        )

        return {
            "save_time_seconds": round(save_time, 2),
            "final_bin_mb": round(final_bin_mb, 2),
            "final_meta_mb": round(final_meta_mb, 2),
            "backup_bin_path": str(backup_bin),
            "backup_meta_path": str(backup_meta),
        }

    def write_json_report(self, report_data: Dict[str, Any]) -> Path:
        """Write the comprehensive sync report JSON file (latest + history archive)."""
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        history_file = HISTORY_DIR / f"faiss_sync_report_{ts_str}.json"

        # Write latest report
        with open(self.report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        # Write archived history report
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        logger.info(f"📊 JSON report written to: {self.report_path.resolve()}")
        logger.info(f"📁 Historical archive saved to: {history_file.resolve()}")
        return self.report_path


async def run_selective_faiss_sync(
    since_date: Optional[str] = None,
    course_code: Optional[str] = None,
    days: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Main orchestrator for Selective FAISS Sync.
    Executes change detection, selective embedding, FAISS index rebuild,
    and detailed before-vs-after JSON reporting.
    """
    start_time = time.time()
    logger.info("=" * 70)
    logger.info("🐬 DOLPHIN FAISS INCREMENTAL / SELECTIVE SYNC ENGINE")
    logger.info(f"Mode: {'DRY RUN (Analysis Only)' if dry_run else 'LIVE SYNC (Re-embed & Update)'}")
    if since_date:
        logger.info(f"Filter: since_date = {since_date}")
    if course_code:
        logger.info(f"Filter: course_code = {course_code}")
    if days is not None:
        logger.info(f"Filter: last {days} days")
    logger.info("=" * 70)

    sync_service = SelectiveFaissSyncService()

    # 1. Load Existing FAISS
    t_load_0 = time.time()
    current_index, current_metadata, before_stats = sync_service.load_existing_faiss()
    t_load = time.time() - t_load_0

    # 2. Fetch DB rows
    t_db_0 = time.time()
    is_full_scan = not (since_date or course_code or days is not None)
    db_rows = await sync_service.fetch_db_candidates(
        since_date=since_date, course_code=course_code, days=days
    )
    t_db = time.time() - t_db_0

    # 3. Analyze differences
    t_diff_0 = time.time()
    analysis = sync_service.analyze_changes(
        existing_metadata=current_metadata,
        db_rows=db_rows,
        is_full_scan=is_full_scan,
    )
    t_diff = time.time() - t_diff_0

    updated_count = len(analysis["updated_topics"])
    new_count = len(analysis["new_topics"])
    deleted_count = len(analysis["deleted_topics"])
    unchanged_count = len(analysis["unchanged_indices"])
    total_to_embed = analysis["total_to_embed"]

    logger.info("-" * 70)
    logger.info("📊 DATABASE CHANGE DETECTION SUMMARY:")
    logger.info(f"  • UNCHANGED Topics (Preserved from FAISS) : {unchanged_count:,}")
    logger.info(f"  • UPDATED Topics (Need re-embedding)     : {updated_count:,}")
    logger.info(f"  • NEW Topics (Need initial embedding)    : {new_count:,}")
    logger.info(f"  • DELETED Topics (Removed from FAISS)    : {deleted_count:,}")
    logger.info(f"  • TOTAL VECTORS TO EMBED                 : {total_to_embed:,}")
    logger.info(f"  • Courses Affected                       : {len(analysis['affected_courses']):,}")
    logger.info("-" * 70)

    # Clean changelog for JSON report (strip internal row_data objects)
    audit_log = []
    for item in analysis["updated_topics"] + analysis["new_topics"] + analysis["deleted_topics"]:
        clean_item = {k: v for k, v in item.items() if k != "row_data"}
        audit_log.append(clean_item)

    # 4. If Dry Run or No Changes
    if dry_run or total_to_embed == 0 and deleted_count == 0:
        total_duration = time.time() - start_time
        status = "NO_CHANGES_NEEDED" if total_to_embed == 0 and deleted_count == 0 else "DRY_RUN_COMPLETED"
        logger.info(f"🏁 Execution finished with status: {status} in {total_duration:.2f}s")

        report_data = {
            "summary": {
                "status": status,
                "execution_timestamp": datetime.datetime.now().isoformat(),
                "total_duration_seconds": round(total_duration, 2),
                "total_duration_formatted": format_seconds(total_duration),
                "dry_run": dry_run,
                "filter_applied": {
                    "since_date": since_date,
                    "course_code": course_code,
                    "days": days,
                    "full_scan": is_full_scan,
                },
            },
            "time_breakdown_seconds": {
                "load_existing_faiss": round(t_load, 2),
                "db_query_time": round(t_db, 2),
                "diff_analysis_time": round(t_diff, 2),
                "embedding_generation_time": 0.0,
                "faiss_rebuild_time": 0.0,
                "disk_save_time": 0.0,
                "total_seconds": round(total_duration, 2),
            },
            "before_update": before_stats,
            "after_update": {
                **before_stats,
                "note": "No modifications applied (Dry Run or No Changes Detected)",
            },
            "diff_summary": {
                "unchanged_topics_count": unchanged_count,
                "updated_topics_count": updated_count,
                "new_topics_count": new_count,
                "deleted_topics_count": deleted_count,
                "total_vectors_to_embed": total_to_embed,
                "estimated_tokens": total_to_embed * 600,
                "estimated_cost_usd": round((total_to_embed * 600 / 1_000_000) * 0.13, 4),
                "affected_courses_count": len(analysis["affected_courses"]),
                "affected_courses_breakdown": analysis["affected_courses"],
            },
            "changed_topics_audit_log": audit_log,
        }
        sync_service.write_json_report(report_data)
        await close_pool()
        return report_data

    # 5. Live Embedding Generation for Changed Topics Only
    items_to_embed = analysis["updated_topics"] + analysis["new_topics"]
    new_embeddings, embed_sec, tokens_used = await sync_service.generate_embeddings_for_diff(
        items_to_embed
    )

    # 6. Reconstruct & Merge FAISS index
    new_index, new_metadata, rebuild_stats = sync_service.execute_sync(
        current_index=current_index,
        current_metadata=current_metadata,
        analysis=analysis,
        new_embeddings=new_embeddings,
    )

    # 7. Atomic Save to Disk
    save_stats = sync_service.save_atomic_with_backup(new_index, new_metadata)

    # 8. Post-Sync Dynamic Cache Refresh
    try:
        from services.dynamic_acronym_service import dynamic_acronym_service
        from services.dynamic_domain_service import dynamic_domain_service

        dynamic_domain_service.clear_cache()
        await dynamic_domain_service.harvest_course_topics()
        await dynamic_acronym_service.harvest_course_acronyms()
        logger.info("✓ Dynamic domain and acronym caches refreshed successfully.")
    except Exception as e:
        logger.warning(f"Note: Dynamic service cache refresh skipped or non-critical: {e}")

    total_duration = time.time() - start_time

    # Compute 'after' stats
    after_courses = set()
    for m in new_metadata:
        c = m.get("course_code")
        if c:
            after_courses.add(c)

    after_stats = {
        "total_vectors": new_index.ntotal,
        "total_topics_in_meta": len(new_metadata),
        "distinct_courses_in_meta": len(after_courses),
        "index_file_size_mb": save_stats["final_bin_mb"],
        "meta_file_size_mb": save_stats["final_meta_mb"],
        "new_vectors_added": new_count,
        "updated_vectors_replaced": updated_count,
        "stale_vectors_deleted": deleted_count,
        "unchanged_vectors_preserved": unchanged_count,
    }

    report_data = {
        "summary": {
            "status": "SUCCESS",
            "execution_timestamp": datetime.datetime.now().isoformat(),
            "total_duration_seconds": round(total_duration, 2),
            "total_duration_formatted": format_seconds(total_duration),
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimension": EMBEDDING_DIM,
            "filter_applied": {
                "since_date": since_date,
                "course_code": course_code,
                "days": days,
                "full_scan": is_full_scan,
            },
        },
        "time_breakdown_seconds": {
            "load_existing_faiss": round(t_load, 2),
            "db_query_time": round(t_db, 2),
            "diff_analysis_time": round(t_diff, 2),
            "embedding_generation_time": round(embed_sec, 2),
            "faiss_rebuild_time": rebuild_stats["rebuild_time_seconds"],
            "disk_save_time": save_stats["save_time_seconds"],
            "total_seconds": round(total_duration, 2),
            "total_formatted": format_seconds(total_duration),
        },
        "before_update": before_stats,
        "after_update": after_stats,
        "diff_summary": {
            "unchanged_topics_count": unchanged_count,
            "updated_topics_count": updated_count,
            "new_topics_count": new_count,
            "deleted_topics_count": deleted_count,
            "total_vectors_embedded": total_to_embed,
            "tokens_used": tokens_used,
            "estimated_cost_usd": round((tokens_used / 1_000_000) * 0.13, 4),
            "affected_courses_count": len(analysis["affected_courses"]),
            "affected_courses_breakdown": analysis["affected_courses"],
        },
        "changed_topics_audit_log": audit_log,
    }

    sync_service.write_json_report(report_data)
    await close_pool()

    logger.info("=" * 70)
    logger.success(
        f"🎉 FAISS SELECTIVE SYNC COMPLETED SUCCESSFULLY in {format_seconds(total_duration)}!"
    )
    logger.info(
        f"   Vectors Before: {before_stats['total_vectors']:,}  ➡️  "
        f"Vectors After: {after_stats['total_vectors']:,}"
    )
    logger.info(f"   Updated: {updated_count} | New: {new_count} | Deleted: {deleted_count} | Kept: {unchanged_count:,}")
    logger.info(f"   Report file: {REPORT_PATH.name}")
    logger.info("=" * 70)

    return report_data


def parse_args():
    parser = argparse.ArgumentParser(
        description="Selective / Incremental FAISS Synchronization from PostgreSQL course_content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        "--check-only",
        dest="dry_run",
        action="store_true",
        help="Check and display changes, tokens, and estimated time without modifying FAISS index.",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Only check topics fetched/updated on or after YYYY-MM-DD.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Only check topics fetched/updated in the last N days.",
    )
    parser.add_argument(
        "--course",
        type=str,
        default=None,
        help="Sync a specific course code only (e.g. BBSV-1002-...).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(
            run_selective_faiss_sync(
                since_date=args.since,
                course_code=args.course,
                days=args.days,
                dry_run=args.dry_run,
            )
        )
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Operation cancelled by user.")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"❌ Selective FAISS Sync failed: {exc}")
        logger.exception(exc)
        sys.exit(1)
