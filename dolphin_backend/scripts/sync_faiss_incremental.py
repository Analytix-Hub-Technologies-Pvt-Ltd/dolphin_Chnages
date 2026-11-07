#!/usr/bin/env python3
"""
scripts/sync_faiss_incremental.py
=================================
CLI shortcut to run the Incremental / Selective FAISS Sync Engine.

Examples:
    # 1. Dry run - inspect DB changes, time estimates & report without modifying index:
    python scripts/sync_faiss_incremental.py --dry-run

    # 2. Check & sync topics updated since a date (e.g., 2026-07-01):
    python scripts/sync_faiss_incremental.py --since 2026-07-01

    # 3. Check & sync only topics from the last 7 days:
    python scripts/sync_faiss_incremental.py --days 7

    # 4. Sync a single specific course:
    python scripts/sync_faiss_incremental.py --course <course_code>

    # 5. Full sync across all courses:
    python scripts/sync_faiss_incremental.py
"""

import sys
import asyncio
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.selective_faiss_sync import parse_args, run_selective_faiss_sync

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
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
