# Database Baseline Schema: `dolphintest`

**Extracted On:** September 7, 2026  
**Host:** `127.0.0.1:5432`  
**Database:** `dolphintest`  
**Total Tables:** 12  

---

## Summary of Tables

| # | Table Name | Columns | Description |
|---|---|---|---|
| 1 | [`chat_sessions`](#1-chat_sessions) | 8 | Tracks active chat sessions for users |
| 2 | [`course_content`](#2-course_content) | 9 | Extracted sections, topics, lessons, and content for courses |
| 3 | [`course_content_backup`](#3-course_content_backup) | 9 | Backup snapshot of course content table |
| 4 | [`master_course_data`](#4-master_course_data) | 4 | Master registry of available courses and course metadata |
| 5 | [`master_course_data_backup`](#5-master_course_data_backup) | 4 | Backup snapshot of master course data table |
| 6 | [`message_feedback`](#6-message_feedback) | 11 | User ratings and feedback on AI responses |
| 7 | [`open_ai_log`](#7-open_ai_log) | 6 | Audit log for OpenAI LLM and embedding calls |
| 8 | [`saved_chats`](#8-saved_chats) | 3 | Stored conversation messages between users and the AI tutor |
| 9 | [`tutor_content`](#9-tutor_content) | 7 | Primary source content indexed into FAISS vector store |
| 10 | [`user_memories`](#10-user_memories) | 4 | Long-term extracted user preferences, facts, and context |
| 11 | [`user_roles`](#11-user_roles) | 2 | Role definitions and permissions (e.g. Admin, Student, Captain) |
| 12 | [`users`](#12-users) | 19 | User accounts, authentication credentials, and profile settings |

---

### 1. `chat_sessions`
*Tracks active chat sessions for users*

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| **`session_id`** | `text` | No | - | 🔑 PRIMARY KEY |
| **`user_id`** | `text` | Yes | `'anonymous'::text` | - |
| **`created_at`** | `timestamp without time zone` | Yes | `CURRENT_TIMESTAMP` | - |
| **`updated_at`** | `timestamp without time zone` | Yes | `CURRENT_TIMESTAMP` | - |
| **`messages`** | `jsonb` | Yes | `'[]'::jsonb` | - |
| **`metadata`** | `jsonb` | Yes | `'{}'::jsonb` | - |
| **`title`** | `text` | Yes | - | - |
| **`is_saved`** | `boolean` | Yes | `false` | - |

---

### 2. `course_content`
*Extracted sections, topics, lessons, and content for courses*

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| **`content_id`** | `bigint` | No | - | - |
| **`course_code`** | `text` | No | - | - |
| **`topic_code`** | `text` | No | - | - |
| **`topic_name`** | `text` | No | - | - |
| **`topic_video`** | `jsonb` | No | - | - |
| **`topic_image`** | `jsonb` | No | - | - |
| **`topic_pdf`** | `jsonb` | No | - | - |
| **`topic_content`** | `text` | No | - | - |
| **`fetched_on`** | `date` | No | - | - |

**Indexes:**
- `course_content_content_id_idx`: `CREATE INDEX course_content_content_id_idx ON public.course_content USING btree (content_id)`
- `course_content_fetched_on_idx`: `CREATE INDEX course_content_fetched_on_idx ON public.course_content USING btree (fetched_on)`

---

### 3. `course_content_backup`
*Backup snapshot of course content table*

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| **`content_id`** | `bigint` | No | - | - |
| **`course_code`** | `text` | No | - | - |
| **`topic_code`** | `text` | No | - | - |
| **`topic_name`** | `text` | No | - | - |
| **`topic_video`** | `jsonb` | No | - | - |
| **`topic_image`** | `jsonb` | No | - | - |
| **`topic_pdf`** | `jsonb` | No | - | - |
| **`topic_content`** | `text` | No | - | - |
| **`fetched_on`** | `date` | No | - | - |

---

### 4. `master_course_data`
*Master registry of available courses and course metadata*

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| **`course_id`** | `bigint` | No | - | - |
| **`course_code`** | `text` | No | - | - |
| **`course_name`** | `text` | No | - | - |
| **`course_added`** | `date` | No | - | - |

---

### 5. `master_course_data_backup`
*Backup snapshot of master course data table*

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| **`course_id`** | `bigint` | No | - | - |
| **`course_code`** | `text` | No | - | - |
| **`course_name`** | `text` | No | - | - |
| **`course_added`** | `date` | No | - | - |

---

### 6. `message_feedback`
*User ratings and feedback on AI responses*

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| **`id`** | `integer` | No | `nextval('message_feedback_id_seq'::regclass)` | 🔑 PRIMARY KEY |
| **`session_id`** | `text` | No | - | - |
| **`message_id`** | `text` | No | - | - |
| **`user_id`** | `text` | No | - | - |
| **`rating`** | `text` | No | - | - |
| **`feedback_text`** | `text` | Yes | - | - |
| **`timestamp`** | `timestamp with time zone` | Yes | `CURRENT_TIMESTAMP` | - |
| **`reasons`** | `text[]` | Yes | `'{}'::text[]` | - |
| **`short_topic`** | `text` | Yes | - | - |
| **`user_query`** | `text` | Yes | - | - |
| **`model_response`** | `text` | Yes | - | - |

**Indexes:**
- `idx_message_feedback_session_id`: `CREATE INDEX idx_message_feedback_session_id ON public.message_feedback USING btree (session_id)`
- `idx_message_feedback_short_topic`: `CREATE INDEX idx_message_feedback_short_topic ON public.message_feedback USING btree (short_topic)`

---

### 7. `open_ai_log`
*Audit log for OpenAI LLM and embedding calls*

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| **`id`** | `integer` | No | `nextval('open_ai_log_id_seq'::regclass)` | 🔑 PRIMARY KEY |
| **`input_llm`** | `text` | No | - | - |
| **`output_llm`** | `text` | No | - | - |
| **`query_category`** | `text` | No | - | - |
| **`created_at`** | `timestamp without time zone` | Yes | `CURRENT_TIMESTAMP` | - |
| **`updated_at`** | `timestamp without time zone` | Yes | `CURRENT_TIMESTAMP` | - |

---

### 8. `saved_chats`
*Stored conversation messages between users and the AI tutor*

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| **`session_id`** | `text` | No | - | 🔑 PRIMARY KEY, 🔗 FK ➔ `chat_sessions.session_id` |
| **`user_id`** | `text` | No | - | 🔑 PRIMARY KEY |
| **`saved_at`** | `timestamp without time zone` | Yes | `CURRENT_TIMESTAMP` | - |

---

### 9. `tutor_content`
*Primary source content indexed into FAISS vector store*

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| **`id`** | `integer` | No | `nextval('tutor_content_id_seq'::regclass)` | 🔑 PRIMARY KEY |
| **`title`** | `text` | No | - | - |
| **`section`** | `text` | No | - | - |
| **`content_text`** | `text` | No | - | - |
| **`videourl`** | `text` | No | - | - |
| **`created_at`** | `timestamp without time zone` | Yes | `now()` | - |
| **`updated_at`** | `timestamp without time zone` | Yes | `now()` | - |

---

### 10. `user_memories`
*Long-term extracted user preferences, facts, and context*

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| **`id`** | `uuid` | No | `gen_random_uuid()` | 🔑 PRIMARY KEY |
| **`user_id`** | `text` | No | - | ✨ UNIQUE (`user_id`, `content`) |
| **`content`** | `text` | No | - | ✨ UNIQUE (`user_id`, `content`) |
| **`created_at`** | `timestamp with time zone` | Yes | `CURRENT_TIMESTAMP` | - |

**Indexes:**
- `idx_user_memories_user_id`: `CREATE INDEX idx_user_memories_user_id ON public.user_memories USING btree (user_id)`
- `unique_user_memory`: `CREATE UNIQUE INDEX unique_user_memory ON public.user_memories USING btree (user_id, content)`

---

### 11. `user_roles`
*Role definitions and permissions (e.g. Admin, Student, Captain)*

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| **`id`** | `integer` | No | `nextval('user_roles_id_seq'::regclass)` | 🔑 PRIMARY KEY |
| **`role_name`** | `character varying(50)` | No | - | ✨ UNIQUE |

**Indexes:**
- `user_roles_role_name_key`: `CREATE UNIQUE INDEX user_roles_role_name_key ON public.user_roles USING btree (role_name)`

---

### 12. `users`
*User accounts, authentication credentials, and profile settings*

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| **`id`** | `text` | No | - | 🔑 PRIMARY KEY |
| **`name`** | `text` | No | - | - |
| **`email`** | `text` | Yes | - | ✨ UNIQUE |
| **`phone_number`** | `text` | Yes | - | - |
| **`birth_date`** | `date` | Yes | - | - |
| **`password_hash`** | `text` | Yes | - | - |
| **`created_at`** | `timestamp without time zone` | Yes | `CURRENT_TIMESTAMP` | - |
| **`updated_at`** | `timestamp without time zone` | Yes | `CURRENT_TIMESTAMP` | - |
| **`user_name`** | `text` | Yes | - | ✨ UNIQUE |
| **`company_name`** | `text` | Yes | - | - |
| **`role`** | `text` | Yes | - | - |
| **`user_type`** | `text` | Yes | - | - |
| **`ship_type`** | `text` | Yes | - | - |
| **`id_type`** | `text` | Yes | - | - |
| **`id_country`** | `text` | Yes | - | - |
| **`user_bio`** | `text` | Yes | - | - |
| **`user_courses`** | `text` | Yes | - | - |
| **`ship_name`** | `text` | Yes | - | - |
| **`role_id`** | `integer` | Yes | `1` | 🔗 FK ➔ `user_roles.id` |

**Indexes:**
- `uq_intbl_user_user_name`: `CREATE UNIQUE INDEX uq_intbl_user_user_name ON public.users USING btree (user_name)`
- `users_email_key`: `CREATE UNIQUE INDEX users_email_key ON public.users USING btree (email)`
