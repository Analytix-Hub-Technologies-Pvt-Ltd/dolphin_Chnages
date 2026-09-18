-- =============================================================================
-- Baseline PostgreSQL Schema: dolphintest
-- Host: 192.168.2.75:5433
-- Extracted On: 2026-09-07 16:39:28
-- Total Tables: 12
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- Table: user_roles
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_roles (
    id SERIAL NOT NULL,
    role_name VARCHAR(50) NOT NULL,
    CONSTRAINT user_roles_pkey PRIMARY KEY (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS user_roles_role_name_key ON public.user_roles USING btree (role_name);

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
    ship_name TEXT,
    ship_type TEXT,
    id_type TEXT,
    id_country TEXT,
    user_bio TEXT,
    user_courses TEXT,
    company_id INTEGER,
    content_type TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    role_id INTEGER DEFAULT 1,
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
-- Table: company_charts
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS company_charts (
    chart_id BIGSERIAL NOT NULL,
    company_id TEXT NOT NULL,
    img_title TEXT,
    image_base64 TEXT NOT NULL,
    chart_json JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT company_charts_pkey PRIMARY KEY (chart_id)
);


-- -----------------------------------------------------------------------------
-- Table: company_documents
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS company_documents (
    document_id BIGSERIAL NOT NULL,
    company_id TEXT NOT NULL,
    document_title TEXT,
    document_content TEXT,
    content_type TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT company_documents_pkey PRIMARY KEY (document_id)
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
-- Table: saved_chats
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS saved_chats (
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    saved_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT saved_chats_pkey PRIMARY KEY (session_id, user_id)
);


-- -----------------------------------------------------------------------------
-- Table: test_transcribe
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS test_transcribe (
    transcribe_id BIGSERIAL NOT NULL,
    course_code TEXT,
    topic_code TEXT,
    video_id TEXT,
    video_link TEXT,
    transcription_content TEXT,
    status TEXT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT transcribe_pkey PRIMARY KEY (transcribe_id)
);


-- -----------------------------------------------------------------------------
-- Table: transcribe
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transcribe (
    transcribe_id BIGSERIAL NOT NULL,
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
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT transcribe_pkey1 PRIMARY KEY (transcribe_id)
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

