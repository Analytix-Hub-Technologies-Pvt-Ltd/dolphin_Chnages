"""
Embedding service configuration for OpenAI text-embedding-3-large.

Performance Optimizations:
- Uses batch embedding API for massive speed improvements
- Recommended batch_size: 500 (can go up to 2048 for OpenAI)
- Checkpoint interval: 2000 rows (saves progress for huge datasets)
"""

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIM = 3072

# Batch processing configuration
EMBEDDING_BATCH_SIZE = 100  # Number of texts per API batch call (reduced for long texts)
CHECKPOINT_INTERVAL = 1000   # Save checkpoint every N rows for crash recovery

# Rate limiting (seconds between batch calls)
BATCH_DELAY = 1.0  # Conservative 1 second delay to avoid rate limits
