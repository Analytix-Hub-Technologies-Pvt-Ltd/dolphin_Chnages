-- =============================================================================
-- Baseline PostgreSQL Schema: dolphinai
-- Host: 192.168.2.75:5433
-- Extracted On: 2026-09-07 16:39:36
-- Total Tables: 6
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

