#!/usr/bin/env python3
"""
Manual script to rebuild FAISS index from PostgreSQL course_content table.
Supports filtering by last N days to avoid processing heavy data.

Usage:
    python scripts/rebuild_faiss_last_days.py           # Rebuild from ALL data
    python scripts/rebuild_faiss_last_days.py --days 1  # Last 1 day only
    python scripts/rebuild_faiss_last_days.py --days 7  # Last 7 days
"""

import asyncio
import sys
import argparse
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from retrieval.faiss_store import FAISSStore
from retrieval.refresh_chunks import rebuild_faiss_index


async def main(days: Optional[int] = None):
    """
    Rebuild FAISS index from PostgreSQL.
    
    Args:
        days: If specified, only process rows from last N days. If None, process all.
    """
    print("=" * 60)
    print("FAISS Index Rebuild Script")
    print("=" * 60)
    
    if days:
        print(f"Mode: Last {days} day(s) only")
        print(f"This will read data from the last {days} day(s) from course_content table")
    else:
        print("Mode: ALL data")
        print("This will read ALL data from course_content table in PostgreSQL")
    
    print("Generating embeddings (this may take a few minutes)...\n")

    store = FAISSStore()
    await rebuild_faiss_index(store, days=days)

    print("\n" + "=" * 60)
    print("FAISS rebuild completed successfully!")
    print(f"Index saved to: {store.index_path}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rebuild FAISS index from PostgreSQL course_content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/rebuild_faiss_last_days.py                # Rebuild from ALL data
  python scripts/rebuild_faiss_last_days.py --days 1       # Last 1 day only
  python scripts/rebuild_faiss_last_days.py --days 7       # Last 7 days
        """
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Only process data from last N days. If not specified, processes all data."
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main(days=args.days))
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
