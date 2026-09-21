-- =============================================================================
-- Baseline PostgreSQL Schema: dolphintest
-- Database: dolphintest
-- Extracted: 2026-09-07
-- Total Tables: 12
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. Table: user_roles
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_roles (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

-- -----------------------------------------------------------------------------
-- 2. Table: users
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone_number TEXT,
    birth_date DATE,
    password_hash TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_name TEXT UNIQUE,
    company_name TEXT,
    role TEXT,
    user_type TEXT,
    ship_type TEXT,
    id_type TEXT,
    id_country TEXT,
    user_bio TEXT,
    user_courses TEXT,
    ship_name TEXT,
    role_id INTEGER DEFAULT 1 REFERENCES user_roles(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_intbl_user_user_name ON users (user_name);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_key ON users (email);

-- -----------------------------------------------------------------------------
-- 3. Table: chat_sessions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT 'anonymous',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    messages JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    title TEXT,
    is_saved BOOLEAN DEFAULT false
);

-- -----------------------------------------------------------------------------
-- 4. Table: saved_chats
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS saved_chats (
    session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    saved_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_saved_chats PRIMARY KEY (session_id, user_id)
);

-- -----------------------------------------------------------------------------
-- 5. Table: user_memories
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_memory UNIQUE (user_id, content)
);

CREATE INDEX IF NOT EXISTS idx_user_memories_user_id ON user_memories (user_id);

-- -----------------------------------------------------------------------------
-- 6. Table: tutor_content
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tutor_content (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    section TEXT NOT NULL,
    content_text TEXT NOT NULL,
    videourl TEXT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 7. Table: course_content
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS course_content (
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

CREATE INDEX IF NOT EXISTS course_content_content_id_idx ON course_content (content_id);
CREATE INDEX IF NOT EXISTS course_content_fetched_on_idx ON course_content (fetched_on);

-- -----------------------------------------------------------------------------
-- 8. Table: course_content_backup
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

-- -----------------------------------------------------------------------------
-- 9. Table: master_course_data
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS master_course_data (
    course_id BIGINT NOT NULL,
    course_code TEXT NOT NULL,
    course_name TEXT NOT NULL,
    course_added DATE NOT NULL
);

-- -----------------------------------------------------------------------------
-- 10. Table: master_course_data_backup
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS master_course_data_backup (
    course_id BIGINT NOT NULL,
    course_code TEXT NOT NULL,
    course_name TEXT NOT NULL,
    course_added DATE NOT NULL
);

-- -----------------------------------------------------------------------------
-- 11. Table: message_feedback
-- -----------------------------------------------------------------------------
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
-- 12. Table: open_ai_log
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS open_ai_log (
    id SERIAL PRIMARY KEY,
    input_llm TEXT NOT NULL,
    output_llm TEXT NOT NULL,
    query_category TEXT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
