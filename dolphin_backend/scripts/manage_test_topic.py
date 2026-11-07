#!/usr/bin/env python3
"""
scripts/manage_test_topic.py
============================
Utility to safely alter a test topic in PostgreSQL course_content to test FAISS selective sync,
and cleanly restore the original topic name and FAISS index afterward.

Target Test Record:
  content_id: 51658
  topic_code: 4433e4e9-950c-e711-80c0-000c29b080c2
  course_code: a30d62e9-e6cc-e611-80bf-000c29b080c2
  original_topic_name: "Class as a RO and RSO"
  altered_topic_name:  "Class as a RO and RSO (TEST ALTERATION)"
"""

import sys
import shutil
import asyncio
import argparse
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models.database import get_pool, close_pool

CONTENT_ID = 51658
COURSE_CODE = "a30d62e9-e6cc-e611-80bf-000c29b080c2"
TOPIC_CODE = "4433e4e9-950c-e711-80c0-000c29b080c2"
ORIGINAL_NAME = "Class as a RO and RSO"
ALTERED_NAME = "Class as a RO and RSO (TEST ALTERATION)"

INDEX_PATH = BACKEND_DIR / "retrieval" / "faiss_index.bin"
META_PATH = BACKEND_DIR / "retrieval" / "faiss_index.meta.json"
BACKUP_INDEX_PATH = BACKEND_DIR / "retrieval" / "faiss_index.bin.bak"
BACKUP_META_PATH = BACKEND_DIR / "retrieval" / "faiss_index.meta.meta.json.bak"


async def check_status():
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT content_id, course_code, topic_code, topic_name, fetched_on FROM course_content WHERE content_id = $1",
        CONTENT_ID,
    )
    print("=" * 60)
    print("STATUS CHECK")
    print("=" * 60)
    if row:
        print(f"PostgreSQL DB topic_name: '{row['topic_name']}'")
        print(f"Content ID: {row['content_id']}")
        print(f"Course Code: {row['course_code']}")
        print(f"Topic Code:  {row['topic_code']}")
        is_altered = row['topic_name'] == ALTERED_NAME
        print(f"DB State:    {'[ALTERED FOR TESTING]' if is_altered else '[ORIGINAL]'}")
    else:
        print("Record not found in DB!")
    
    print("-" * 60)
    print(f"FAISS index exists:      {INDEX_PATH.exists()} ({INDEX_PATH.stat().st_size / (1024*1024):.1f} MB)" if INDEX_PATH.exists() else "FAISS index missing")
    print(f"FAISS backup exists:     {BACKUP_INDEX_PATH.exists()} ({BACKUP_INDEX_PATH.stat().st_size / (1024*1024):.1f} MB)" if BACKUP_INDEX_PATH.exists() else "FAISS backup missing")
    print(f"Metadata backup exists:  {BACKUP_META_PATH.exists()} ({BACKUP_META_PATH.stat().st_size / (1024*1024):.1f} MB)" if BACKUP_META_PATH.exists() else "Metadata backup missing")
    print("=" * 60)
    await close_pool()


async def alter_topic():
    pool = await get_pool()
    await pool.execute(
        "UPDATE course_content SET topic_name = $1 WHERE content_id = $2",
        ALTERED_NAME,
        CONTENT_ID,
    )
    print(f"Successfully altered topic (content_id={CONTENT_ID}) to:\n  '{ALTERED_NAME}'")
    await close_pool()


async def revert_topic():
    pool = await get_pool()
    await pool.execute(
        "UPDATE course_content SET topic_name = $1 WHERE content_id = $2",
        ORIGINAL_NAME,
        CONTENT_ID,
    )
    print(f"Successfully reverted topic (content_id={CONTENT_ID}) to original name:\n  '{ORIGINAL_NAME}'")
    await close_pool()


def restore_faiss():
    if not BACKUP_INDEX_PATH.exists():
        print(f"Error: Backup index not found at {BACKUP_INDEX_PATH}")
        return
    if not BACKUP_META_PATH.exists():
        print(f"Error: Backup meta not found at {BACKUP_META_PATH}")
        return

    print("Restoring FAISS index and metadata from backups...")
    shutil.copy2(BACKUP_INDEX_PATH, INDEX_PATH)
    shutil.copy2(BACKUP_META_PATH, META_PATH)
    print("FAISS index and metadata successfully restored to pre-test state!")


def main():
    parser = argparse.ArgumentParser(description="Manage test topic for FAISS selective sync")
    parser.add_argument("--status", action="store_true", help="Check current DB and FAISS status")
    parser.add_argument("--alter", action="store_true", help="Alter topic name in DB to test value")
    parser.add_argument("--revert-db", action="store_true", help="Revert topic name in DB to original value")
    parser.add_argument("--restore-faiss", action="store_true", help="Restore FAISS files from backup")

    args = parser.parse_args()

    if args.alter:
        asyncio.run(alter_topic())
    elif args.revert_db:
        asyncio.run(revert_topic())
    elif args.restore_faiss:
        restore_faiss()
    else:
        asyncio.run(check_status())


if __name__ == "__main__":
    main()
