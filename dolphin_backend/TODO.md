# Project TODO & Pending Tasks

Last Updated: 2026-09-07

---

## 1. Database Synchronization (Postponed for Later Application)

### Objective
Unify the schema and synchronize critical data across **Local (`127.0.0.1:5432`)** and **Remote (`192.168.2.75:5433`)** so all features (Company Gap Analysis, Audio Transcription, Long-Term User Memories, and RBAC) function identically in all environments.

### Schema Differences Summary
- **Local `dolphintest` vs Remote `dolphintest`:**
  - **Missing in Local:** 
    - Tables: `company_documents` (37 rows), `company_charts` (0 rows), `transcribe` (7,237 rows), `test_transcribe` (35,468 rows).
    - `users` columns: `is_admin`, `company_id`, `content_type`.
  - **Missing in Remote:**
    - Tables: `user_memories` (201 rows), `message_feedback` (0 rows), `course_content_backup` (51,876 rows), `master_course_data_backup` (1,110 rows).
- **Remote `dolphindb`:** Contains `user_memories` and backup snapshots, but lacks `user_roles`, `company_documents`, and `transcribe`.

### Action Items
- [ ] **Apply Unified Schema Migration:**
  - File: [`sql/sync_migration.sql`](file:///c:/Projects/Vijay/dolphin-api/sql/sync_migration.sql)
  - Execute on Local PostgreSQL (`127.0.0.1:5432/dolphintest`).
  - Execute on Remote PostgreSQL (`192.168.2.75:5433/dolphintest`).
  - *(Note: Dry-run test has already verified clean syntax and zero conflicts on both targets).*
- [ ] **Migrate Missing Data:**
  - [ ] Copy the 201 `user_memories` records from Local / `dolphindb` into Remote `dolphintest` so user conversational memory is restored.
  - [ ] Copy the 37 `company_documents` records from Remote `dolphintest` into Local `dolphintest` so `/companies/check-gaps` can run completely offline without VPN.
- [ ] **Re-verify with Automation Scripts:**
  - Run [`scripts/compare_dbs.py`](file:///c:/Projects/Vijay/dolphin-api/scripts/compare_dbs.py) to confirm 0 schema differences and matching row counts.
  - Run [`scripts/extract_all_baselines.py`](file:///c:/Projects/Vijay/dolphin-api/scripts/extract_all_baselines.py) to refresh the baseline documents in `sql/`.

---

## 2. Git Branch & Merge Tasks

- [ ] **Final Merge to `development` (User-Assigned):**
  - Merge verified branch `copy-dev-temp` into `development`.
  - Push merged `development` to remote `origin/development`.
  - Archive or delete temporary branches (`copy-dev-temp`, `feature/Dolphin_new_changes-BackendAH`).

---

## 3. Testing & Verification

- [ ] **Live Integration Tests:**
  - Set `RUN_LIVE_SERVER_TESTS=1` and execute `pytest tests/test_gap_check_api.py`.
  - Validate response payload against newly synchronized `company_documents`.
- [ ] **OpenAI Credentials Check:**
  - Validate active API keys in `.env` for production endpoints.
- [ ] **FAISS Vector Store Monitoring:**
  - Ensure 53,840 vector index remains aligned with `course_content` and `tutor_content` tables.

---

## Reference Tools & Artifacts

| Tool / File | Location | Description |
|---|---|---|
| Migration Script | [`sql/sync_migration.sql`](file:///c:/Projects/Vijay/dolphin-api/sql/sync_migration.sql) | Idempotent DDL to create missing tables and columns |
| Dry-Run Test Script | [`scripts/test_sync_migration.py`](file:///c:/Projects/Vijay/dolphin-api/scripts/test_sync_migration.py) | Executes `sync_migration.sql` in a rollback transaction |
| DB Comparison Tool | [`scripts/compare_dbs.py`](file:///c:/Projects/Vijay/dolphin-api/scripts/compare_dbs.py) | Compares tables, columns, constraints, and live row counts |
| Baseline Generator | [`scripts/extract_all_baselines.py`](file:///c:/Projects/Vijay/dolphin-api/scripts/extract_all_baselines.py) | Extracts and documents schema for all target databases |
| Baseline Documentation | [`sql/`](file:///c:/Projects/Vijay/dolphin-api/sql) | Host-specific `.md` and `.sql` baseline files |
