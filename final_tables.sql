--
-- PostgreSQL database dump
--

\restrict TgdPGn7YJD4YocID309NHcdLLTzUGECl09Qmt0N6oOBfjiObRMvfyUEc6Lf2dQc

-- Dumped from database version 15.14 (Debian 15.14-1.pgdg12+1)
-- Dumped by pg_dump version 16.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: chat_sessions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.chat_sessions (
    session_id text NOT NULL,
    user_id text DEFAULT 'anonymous'::text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    messages jsonb DEFAULT '[]'::jsonb,
    metadata jsonb DEFAULT '{}'::jsonb,
    title text
);


ALTER TABLE public.chat_sessions OWNER TO postgres;

--
-- Name: course_content; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.course_content (
    content_id bigint NOT NULL,
    course_code text NOT NULL,
    topic_code text NOT NULL,
    topic_name text NOT NULL,
    topic_video jsonb NOT NULL,
    topic_image jsonb NOT NULL,
    topic_pdf jsonb NOT NULL,
    topic_content text NOT NULL,
    fetched_on date NOT NULL
);


ALTER TABLE public.course_content OWNER TO postgres;

--
-- Name: course_content_content_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.course_content ALTER COLUMN content_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.course_content_content_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: master_course_data; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.master_course_data (
    course_id bigint NOT NULL,
    course_code text NOT NULL,
    course_name text NOT NULL,
    course_added date NOT NULL
);


ALTER TABLE public.master_course_data OWNER TO postgres;

--
-- Name: master_course_data_course_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.master_course_data ALTER COLUMN course_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.master_course_data_course_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: open_ai_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.open_ai_log (
    id integer NOT NULL,
    input_llm text NOT NULL,
    output_llm text NOT NULL,
    query_category text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.open_ai_log OWNER TO postgres;

--
-- Name: open_ai_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.open_ai_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.open_ai_log_id_seq OWNER TO postgres;

--
-- Name: open_ai_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.open_ai_log_id_seq OWNED BY public.open_ai_log.id;


--
-- Name: tutor_content; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tutor_content (
    id integer NOT NULL,
    title text NOT NULL,
    section text NOT NULL,
    content_text text NOT NULL,
    videourl text NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.tutor_content OWNER TO postgres;

--
-- Name: tutor_content_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tutor_content_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tutor_content_id_seq OWNER TO postgres;

--
-- Name: tutor_content_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tutor_content_id_seq OWNED BY public.tutor_content.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id text NOT NULL,
    name text NOT NULL,
    email text NOT NULL,
    phone_number text,
    birth_date date,
    password_hash text NOT NULL,
    is_admin boolean DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: open_ai_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.open_ai_log ALTER COLUMN id SET DEFAULT nextval('public.open_ai_log_id_seq'::regclass);


--
-- Name: tutor_content id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tutor_content ALTER COLUMN id SET DEFAULT nextval('public.tutor_content_id_seq'::regclass);


--
-- Name: chat_sessions chat_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chat_sessions
    ADD CONSTRAINT chat_sessions_pkey PRIMARY KEY (session_id);


--
-- Name: open_ai_log open_ai_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.open_ai_log
    ADD CONSTRAINT open_ai_log_pkey PRIMARY KEY (id);


--
-- Name: tutor_content tutor_content_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tutor_content
    ADD CONSTRAINT tutor_content_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


ALTER TABLE public.users
ADD CONSTRAINT users_company_id_unique UNIQUE (company_id);

CREATE TABLE IF NOT EXISTS public.company_documents (
    document_id BIGSERIAL PRIMARY KEY,
    company_id TEXT NOT NULL,
    document_title TEXT,
    document_content TEXT,
    content_type TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.transcribe (
    transcribe_id           BIGSERIAL PRIMARY KEY,
    course_code             TEXT,
    topic_code              TEXT,
    video_id                TEXT,
    video_link              TEXT,
    video_title             TEXT,
    video_duration          TEXT,
    video_thumbnail         TEXT,
    transcription_content   TEXT,
    status                  TEXT,
    error_message           TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
--
-- PostgreSQL database dump complete
--

\unrestrict TgdPGn7YJD4YocID309NHcdLLTzUGECl09Qmt0N6oOBfjiObRMvfyUEc6Lf2dQc
