#!/usr/bin/env python3
"""
Manual script to rebuild FAISS index from PostgreSQL course_content table.
Run this after updating PostgresSQL data (e.g., Dec 26th data).
"""
import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from retrieval.faiss_store import FAISSStore
from retrieval.refresh_chunks import rebuild_faiss_index

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'faiss_rebuild_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """Rebuild FAISS index from PostgreSQL with progress tracking."""
    try:
        logger.info("="*60)
        logger.info("Starting manual FAISS rebuild...")
        logger.info("Reading from course_content table in PostgreSQL")
        logger.info("="*60)
        
        start_time = datetime.now()
        
        # Initialize store
        store = FAISSStore()
        
        # Check if index file exists and backup
        index_path = Path(store.index_path)
        if index_path.exists():
            backup_path = index_path.with_suffix('.bin.backup')
            logger.info(f"Backing up existing index to {backup_path}")
            index_path.rename(backup_path)
        
        # Rebuild with error handling
        logger.info("Starting index rebuild (may take several minutes)...")
        await rebuild_faiss_index(store, days=1)  # Process only last 1 day (20K rows for testing)
        
        # Verify the index was created
        index_path = Path(store.index_path)
        if not index_path.exists():
            raise Exception(f"Index file was not created at {store.index_path}")
        
        file_size = index_path.stat().st_size
        if file_size == 0:
            raise Exception("Index file is empty (0 bytes)!")
        
        # Log success metrics
        duration = datetime.now() - start_time
        logger.info("="*60)
        logger.info("FAISS rebuild completed successfully!")
        logger.info(f"Index saved to: {store.index_path}")
        logger.info(f"File size: {file_size / (1024*1024):.2f} MB")
        logger.info(f"Duration: {duration}")
        logger.info("="*60)
        
        return 0
        
    except Exception as e:
        logger.error("="*60)
        logger.error(f"FAISS rebuild FAILED: {str(e)}", exc_info=True)
        logger.error("="*60)
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
