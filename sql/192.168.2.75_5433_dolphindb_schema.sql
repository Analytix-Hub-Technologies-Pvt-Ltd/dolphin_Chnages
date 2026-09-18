-- =============================================================================
-- Baseline PostgreSQL Schema: dolphindb
-- Host: 192.168.2.75:5433
-- Extracted On: 2026-09-07 16:39:32
-- Total Tables: 11
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- Table: users
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT,
    phone_number TEXT,
    birth_date DATE,
    password_hash TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_name TEXT,
    company_name TEXT,
    role TEXT,
    user_type TEXT,
    ship_type TEXT,
    id_type TEXT,
    id_country TEXT,
    user_bio TEXT,
    user_courses TEXT,
    ship_name TEXT,
    role_id INTEGER,
    CONSTRAINT users_pkey PRIMARY KEY (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_intbl_user_user_name ON public.users USING btree (user_name);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_key ON public.users USING btree (email);

-- -----------------------------------------------------------------------------
-- Table: chat_sessions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id TEXT NOT NULL,
    user_id TEXT DEFAULT 'anonymous'::text,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    messages JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    title TEXT,
    is_saved BOOLEAN DEFAULT false,
    CONSTRAINT chat_sessions_pkey PRIMARY KEY (session_id)
);


-- -----------------------------------------------------------------------------
-- Table: course_content
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

CREATE INDEX IF NOT EXISTS course_content_content_id_idx ON public.course_content USING btree (content_id);
CREATE INDEX IF NOT EXISTS course_content_fetched_on_idx ON public.course_content USING btree (fetched_on);

-- -----------------------------------------------------------------------------
-- Table: course_content_backup
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
-- Table: master_course_data
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS master_course_data (
    course_id BIGINT NOT NULL,
    course_code TEXT NOT NULL,
    course_name TEXT NOT NULL,
    course_added DATE NOT NULL
);


-- -----------------------------------------------------------------------------
-- Table: master_course_data_backup
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS master_course_data_backup (
    course_id BIGINT NOT NULL,
    course_code TEXT NOT NULL,
    course_name TEXT NOT NULL,
    course_added DATE NOT NULL
);


-- -----------------------------------------------------------------------------
-- Table: message_feedback
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS message_feedback (
    id SERIAL NOT NULL,
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    rating TEXT NOT NULL,
    feedback_text TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reasons text[] DEFAULT '{}'::text[],
    short_topic TEXT,
    user_query TEXT,
    model_response TEXT,
    CONSTRAINT message_feedback_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_message_feedback_session_id ON public.message_feedback USING btree (session_id);
CREATE INDEX IF NOT EXISTS idx_message_feedback_short_topic ON public.message_feedback USING btree (short_topic);

-- -----------------------------------------------------------------------------
-- Table: open_ai_log
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS open_ai_log (
    id SERIAL NOT NULL,
    input_llm TEXT NOT NULL,
    output_llm TEXT NOT NULL,
    query_category TEXT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT open_ai_log_pkey PRIMARY KEY (id)
);


-- -----------------------------------------------------------------------------
-- Table: saved_chats
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS saved_chats (
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    saved_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT saved_chats_pkey PRIMARY KEY (session_id, user_id)
);


-- -----------------------------------------------------------------------------
-- Table: tutor_content
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tutor_content (
    id SERIAL NOT NULL,
    title TEXT NOT NULL,
    section TEXT NOT NULL,
    content_text TEXT NOT NULL,
    videourl TEXT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    CONSTRAINT tutor_content_pkey PRIMARY KEY (id)
);


-- -----------------------------------------------------------------------------
-- Table: user_memories
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_memories (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT user_memories_pkey PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_user_memories_user_id ON public.user_memories USING btree (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS unique_user_memory ON public.user_memories USING btree (user_id, content);
