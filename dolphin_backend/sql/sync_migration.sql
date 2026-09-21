-- =============================================================================
-- DOLPHIN DATABASE UNIFICATION & SYNC MIGRATION SCRIPT
-- Purpose: Harmonize schemas across Local (127.0.0.1) and Remote (192.168.2.75)
-- Safe & Idempotent: Uses IF NOT EXISTS, ADD COLUMN IF NOT EXISTS
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. Ensure user_roles exists
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_roles (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

INSERT INTO user_roles (id, role_name) VALUES 
    (1, 'User'),
    (2, 'Admin'),
    (3, 'Tutor')
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 2. Synchronize columns on 'users' table
-- -----------------------------------------------------------------------------
ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS content_type TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role_id INTEGER DEFAULT 1;

-- Ensure Foreign Key to user_roles
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_user_role' AND table_name = 'users'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT fk_user_role FOREIGN KEY (role_id) REFERENCES user_roles(id);
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- 3. Company & Gap-Analysis Tables (Missing in Local / dolphindb)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS company_documents (
    document_id BIGSERIAL PRIMARY KEY,
    company_id TEXT NOT NULL,
    document_title TEXT,
    document_content TEXT,
    content_type TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS company_charts (
    chart_id BIGSERIAL PRIMARY KEY,
    company_id TEXT NOT NULL,
    img_title TEXT,
    image_base64 TEXT NOT NULL,
    chart_json JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 4. Transcription Tables (Missing in Local / dolphindb)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transcribe (
    transcribe_id BIGSERIAL PRIMARY KEY,
    course_code TEXT,
    topic_code TEXT,
    video_id TEXT,
    video_link TEXT,
    video_title TEXT,
    video_duration TEXT,
    video_thumbnail TEXT,
    transcription_content TEXT,
    status TEXT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS test_transcribe (
    transcribe_id BIGSERIAL PRIMARY KEY,
    course_code TEXT,
    topic_code TEXT,
    video_id TEXT,
    video_link TEXT,
    transcription_content TEXT,
    status TEXT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 5. User Memories & Feedback Tables (Missing in Remote dolphintest)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_memory UNIQUE (user_id, content)
);

CREATE INDEX IF NOT EXISTS idx_user_memories_user_id ON user_memories (user_id);

CREATE TABLE IF NOT EXISTS message_feedback (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    rating TEXT NOT NULL,
    feedback_text TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reasons TEXT[] DEFAULT '{}'::text[],
    short_topic TEXT,
    user_query TEXT,
    model_response TEXT
);

CREATE INDEX IF NOT EXISTS idx_message_feedback_session_id ON message_feedback (session_id);
CREATE INDEX IF NOT EXISTS idx_message_feedback_short_topic ON message_feedback (short_topic);

-- -----------------------------------------------------------------------------
-- 6. Backup Tables (Missing in Remote dolphintest)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS course_content_backup (
    content_id BIGINT NOT NULL,
    course_code TEXT NOT NULL,
    topic_code TEXT NOT NULL,
    topic_name TEXT NOT NULL,
    topic_video JSONB NOT NULL,
    topic_image JSONB NOT NULL,
    topic_pdf JSONB NOT NULL,
    topic_content TEXT NOT NULL,
    fetched_on DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS master_course_data_backup (
    course_id BIGINT NOT NULL,
    course_code TEXT NOT NULL,
    course_name TEXT NOT NULL,
    course_added DATE NOT NULL
);
