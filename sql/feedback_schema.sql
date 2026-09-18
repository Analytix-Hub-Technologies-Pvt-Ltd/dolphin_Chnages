-- ============================================================
-- Dolphin AI Feedback, Memory & DPO Training Schema
-- ============================================================

-- 1. Main Feedback Records Table
CREATE TABLE IF NOT EXISTS public.feedback_records (
    feedback_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL DEFAULT 'anonymous',
    conversation_id VARCHAR(128),
    message_id VARCHAR(128),
    question TEXT NOT NULL,
    original_response TEXT NOT NULL,
    feedback_type VARCHAR(64) NOT NULL,
    feedback_comment TEXT,
    company_id VARCHAR(128),
    ship_type VARCHAR(128),
    source_metadata JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    preferred_response TEXT,
    rejection_reason TEXT,
    reviewed_by VARCHAR(128),
    reviewed_at TIMESTAMPTZ,
    admin_comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotent column migrations for feedback_records
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS user_id VARCHAR(128) DEFAULT 'anonymous';
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS conversation_id VARCHAR(128);
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS message_id VARCHAR(128);
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS question TEXT;
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS original_response TEXT;
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS feedback_type VARCHAR(64);
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS feedback_comment TEXT;
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS company_id VARCHAR(128);
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS ship_type VARCHAR(128);
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS source_metadata JSONB DEFAULT '{}'::jsonb;
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'pending';
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS preferred_response TEXT;
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(128);
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS admin_comment TEXT;
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE public.feedback_records ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_feedback_status_created ON public.feedback_records(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_company_id ON public.feedback_records(company_id);
CREATE INDEX IF NOT EXISTS idx_feedback_conversation_id ON public.feedback_records(conversation_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON public.feedback_records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON public.feedback_records(feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_ship_type ON public.feedback_records(ship_type);
CREATE INDEX IF NOT EXISTS idx_feedback_reviewed_by ON public.feedback_records(reviewed_by);


-- 2. Approved Feedback Memory (Semantic Vector Memory)
CREATE TABLE IF NOT EXISTS public.approved_feedback_memory (
    memory_id BIGSERIAL PRIMARY KEY,
    feedback_id VARCHAR(64) NOT NULL REFERENCES public.feedback_records(feedback_id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    preferred_response TEXT NOT NULL,
    original_response TEXT NOT NULL,
    company_id VARCHAR(128) NOT NULL,
    ship_type VARCHAR(128),
    embedding JSONB NOT NULL,
    approved_by VARCHAR(128) NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotent column migrations for approved_feedback_memory
ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS feedback_id VARCHAR(64);
ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS question TEXT;
ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS preferred_response TEXT;
ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS original_response TEXT;
ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS company_id VARCHAR(128);
ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS ship_type VARCHAR(128);
ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS embedding JSONB;
ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS approved_by VARCHAR(128);
ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE public.approved_feedback_memory ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_memory_company_ship ON public.approved_feedback_memory(company_id, ship_type);
CREATE INDEX IF NOT EXISTS idx_memory_feedback_id ON public.approved_feedback_memory(feedback_id);


-- 3. DPO Dataset Table
CREATE TABLE IF NOT EXISTS public.dpo_dataset (
    dpo_id BIGSERIAL PRIMARY KEY,
    feedback_id VARCHAR(64) NOT NULL REFERENCES public.feedback_records(feedback_id) ON DELETE CASCADE,
    company_id VARCHAR(128),
    ship_type VARCHAR(128),
    prompt TEXT NOT NULL,
    chosen TEXT NOT NULL,
    rejected TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending_training',
    dataset_version VARCHAR(32) NOT NULL DEFAULT 'v1.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotent column migrations for dpo_dataset
ALTER TABLE public.dpo_dataset ADD COLUMN IF NOT EXISTS feedback_id VARCHAR(64);
ALTER TABLE public.dpo_dataset ADD COLUMN IF NOT EXISTS company_id VARCHAR(128);
ALTER TABLE public.dpo_dataset ADD COLUMN IF NOT EXISTS ship_type VARCHAR(128);
ALTER TABLE public.dpo_dataset ADD COLUMN IF NOT EXISTS prompt TEXT;
ALTER TABLE public.dpo_dataset ADD COLUMN IF NOT EXISTS chosen TEXT;
ALTER TABLE public.dpo_dataset ADD COLUMN IF NOT EXISTS rejected TEXT;
ALTER TABLE public.dpo_dataset ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'pending_training';
ALTER TABLE public.dpo_dataset ADD COLUMN IF NOT EXISTS dataset_version VARCHAR(32) DEFAULT 'v1.0';
ALTER TABLE public.dpo_dataset ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE public.dpo_dataset ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_dpo_status ON public.dpo_dataset(status);
CREATE INDEX IF NOT EXISTS idx_dpo_company_id ON public.dpo_dataset(company_id);


-- 4. DPO Training Jobs Table
CREATE TABLE IF NOT EXISTS public.dpo_training_jobs (
    job_id VARCHAR(64) PRIMARY KEY,
    company_id VARCHAR(128),
    dataset_version VARCHAR(32) NOT NULL DEFAULT 'v1.0',
    example_count INT NOT NULL DEFAULT 0,
    base_model VARCHAR(128) NOT NULL DEFAULT 'gpt-4o-mini',
    output_model VARCHAR(128),
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotent column migrations for dpo_training_jobs
ALTER TABLE public.dpo_training_jobs ADD COLUMN IF NOT EXISTS company_id VARCHAR(128);
ALTER TABLE public.dpo_training_jobs ADD COLUMN IF NOT EXISTS dataset_version VARCHAR(32) DEFAULT 'v1.0';
ALTER TABLE public.dpo_training_jobs ADD COLUMN IF NOT EXISTS example_count INT DEFAULT 0;
ALTER TABLE public.dpo_training_jobs ADD COLUMN IF NOT EXISTS base_model VARCHAR(128) DEFAULT 'gpt-4o-mini';
ALTER TABLE public.dpo_training_jobs ADD COLUMN IF NOT EXISTS output_model VARCHAR(128);
ALTER TABLE public.dpo_training_jobs ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'queued';
ALTER TABLE public.dpo_training_jobs ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE public.dpo_training_jobs ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE public.dpo_training_jobs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE public.dpo_training_jobs ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
ALTER TABLE public.dpo_training_jobs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE public.dpo_training_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_dpo_jobs_status_created ON public.dpo_training_jobs(status, created_at DESC);
