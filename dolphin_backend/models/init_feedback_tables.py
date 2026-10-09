from __future__ import annotations

import asyncpg
from loguru import logger


INIT_FEEDBACK_SQL = """
-- 1. Feedback Records Table
CREATE TABLE IF NOT EXISTS public.feedback_records (
    feedback_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(128) DEFAULT 'anonymous',
    conversation_id VARCHAR(128),
    message_id VARCHAR(128),
    question TEXT NOT NULL,
    original_response TEXT NOT NULL,
    feedback_type VARCHAR(64) NOT NULL,
    feedback_comment TEXT,
    company_id VARCHAR(128),
    ship_type VARCHAR(128),
    source_metadata JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(32) DEFAULT 'pending',
    preferred_response TEXT,
    rejection_reason TEXT,
    reviewed_by VARCHAR(128),
    reviewed_at TIMESTAMPTZ,
    admin_comment TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for feedback_records
CREATE INDEX IF NOT EXISTS idx_fb_status_created ON public.feedback_records (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fb_company_id ON public.feedback_records (company_id);
CREATE INDEX IF NOT EXISTS idx_fb_conversation_id ON public.feedback_records (conversation_id);
CREATE INDEX IF NOT EXISTS idx_fb_created_at ON public.feedback_records (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fb_feedback_type ON public.feedback_records (feedback_type);
CREATE INDEX IF NOT EXISTS idx_fb_ship_type ON public.feedback_records (ship_type);
CREATE INDEX IF NOT EXISTS idx_fb_reviewed_by ON public.feedback_records (reviewed_by);

-- 2. Approved Feedback Memory Table (Real-time Semantic Vector Store)
CREATE TABLE IF NOT EXISTS public.approved_feedback_memory (
    memory_id VARCHAR(64) PRIMARY KEY,
    feedback_id VARCHAR(64) REFERENCES public.feedback_records(feedback_id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    preferred_response TEXT NOT NULL,
    original_response TEXT NOT NULL,
    company_id VARCHAR(128) NOT NULL DEFAULT 'global',
    ship_type VARCHAR(128),
    embedding JSONB,
    approved_by VARCHAR(128) NOT NULL,
    approved_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for approved_feedback_memory
CREATE INDEX IF NOT EXISTS idx_afm_company_ship ON public.approved_feedback_memory (company_id, ship_type);
CREATE INDEX IF NOT EXISTS idx_afm_feedback_id ON public.approved_feedback_memory (feedback_id);
CREATE INDEX IF NOT EXISTS idx_afm_question ON public.approved_feedback_memory (question);

-- 3. Direct Preference Optimization (DPO) Dataset Table
CREATE TABLE IF NOT EXISTS public.dpo_dataset (
    dpo_id BIGSERIAL PRIMARY KEY,
    feedback_id VARCHAR(64) REFERENCES public.feedback_records(feedback_id) ON DELETE CASCADE,
    company_id VARCHAR(128),
    ship_type VARCHAR(128),
    prompt TEXT NOT NULL,
    chosen TEXT NOT NULL,
    rejected TEXT NOT NULL,
    status VARCHAR(32) DEFAULT 'pending_training',
    dataset_version VARCHAR(32) DEFAULT 'v1.0',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dpo_company_id ON public.dpo_dataset (company_id);
CREATE INDEX IF NOT EXISTS idx_dpo_status ON public.dpo_dataset (status);
CREATE INDEX IF NOT EXISTS idx_dpo_dataset_version ON public.dpo_dataset (dataset_version);

-- 4. DPO Training Jobs Table
CREATE TABLE IF NOT EXISTS public.dpo_training_jobs (
    job_id VARCHAR(64) PRIMARY KEY,
    company_id VARCHAR(128),
    dataset_version VARCHAR(32) DEFAULT 'v1.0',
    example_count INT DEFAULT 0,
    base_model VARCHAR(128) DEFAULT 'gpt-4o-mini',
    output_model VARCHAR(128),
    status VARCHAR(32) DEFAULT 'queued',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dpo_jobs_status ON public.dpo_training_jobs (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dpo_jobs_company ON public.dpo_training_jobs (company_id);
"""


async def init_feedback_tables(pool: asyncpg.Pool) -> None:
    """
    Initialize all feedback, semantic memory, and DPO tables with idempotent migrations.
    """
    try:
        async with pool.acquire() as conn:
            # Check if pgvector extension is available and attempt to enable (optional)
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                logger.info("⚡ PostgreSQL pgvector extension verified/enabled")
            except Exception as ext_err:
                logger.debug("ℹ️ pgvector extension not enabled or permission restricted, using JSONB embeddings with cosine similarity: {}", ext_err)

            await conn.execute(INIT_FEEDBACK_SQL)
            logger.success("✅ Feedback, Memory, and DPO database tables initialized successfully")
    except Exception as e:
        logger.error("❌ Failed to initialize feedback database tables: {}", e)
        raise
