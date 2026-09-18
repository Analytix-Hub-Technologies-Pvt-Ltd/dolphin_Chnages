import asyncio
import asyncpg
import os
from datetime import datetime

DATABASE_TARGETS = [
    {
        "host": "127.0.0.1",
        "port": 5432,
        "user": "postgres",
        "password": "CompunetPG@123",
        "dbname": "dolphintest",
        "prefix": "127.0.0.1_5432_dolphintest"
    },
    {
        "host": "192.168.2.75",
        "port": 5433,
        "user": "postgres",
        "password": "5BPXsrDXPS38Qt0v",
        "dbname": "dolphintest",
        "prefix": "192.168.2.75_5433_dolphintest"
    },
    {
        "host": "192.168.2.75",
        "port": 5433,
        "user": "postgres",
        "password": "5BPXsrDXPS38Qt0v",
        "dbname": "dolphindb",
        "prefix": "192.168.2.75_5433_dolphindb"
    },
    {
        "host": "192.168.2.75",
        "port": 5433,
        "user": "postgres",
        "password": "5BPXsrDXPS38Qt0v",
        "dbname": "dolphinai",
        "prefix": "192.168.2.75_5433_dolphinai"
    },
    {
        "host": "192.168.2.75",
        "port": 5433,
        "user": "postgres",
        "password": "5BPXsrDXPS38Qt0v",
        "dbname": "testdolphin",
        "prefix": "192.168.2.75_5433_testdolphin"
    }
]

TABLE_DESCRIPTIONS = {
    "chat_sessions": "Tracks active chat sessions for users",
    "saved_chats": "Stored conversation messages between users and the AI tutor",
    "user_roles": "Role definitions and permissions (e.g. Admin, Student, Captain)",
    "users": "User accounts, authentication credentials, and profile settings",
    "user_memories": "Long-term extracted user preferences, facts, and context",
    "tutor_content": "Primary source content indexed into FAISS vector store",
    "course_content": "Extracted sections, topics, lessons, and content for courses",
    "course_content_backup": "Backup snapshot of course content table",
    "master_course_data": "Master registry of available courses and course metadata",
    "master_course_data_backup": "Backup snapshot of master course data table",
    "message_feedback": "User ratings and feedback on AI responses",
    "open_ai_log": "Audit log for OpenAI LLM and embedding calls",
    "company_charts": "Company organizational and operational hierarchy charts",
    "company_documents": "Uploaded policy, compliance, and gap-analysis documents",
    "transcribe": "Audio transcription logs and speech-to-text outputs",
    "test_transcribe": "Test bench data for audio transcription"
}

async def extract_schema_for_target(target, output_dir="sql"):
    host = target["host"]
    port = target["port"]
    user = target["user"]
    password = target["password"]
    dbname = target["dbname"]
    prefix = target["prefix"]
    
    print(f"\n[+] Extracting schema for {host}:{port} -> {dbname}...")
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname,
            timeout=10
        )
    except Exception as e:
        print(f"[-] FAILED to connect to {host}:{port}/{dbname}: {e}")
        return

    # 1. Fetch tables
    tables_res = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tables = [r['table_name'] for r in tables_res]
    print(f"    Found {len(tables)} tables: {', '.join(tables)}")

    # 2. Fetch columns
    cols_res = await conn.fetch("""
        SELECT 
            table_name, column_name, data_type, udt_name,
            character_maximum_length, is_nullable, column_default,
            ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """)
    columns_by_table = {}
    for c in cols_res:
        t = c['table_name']
        if t not in columns_by_table:
            columns_by_table[t] = []
        columns_by_table[t].append(dict(c))

    # 3. Fetch constraints (PK, UNIQUE, FK, CHECK)
    constraints_res = await conn.fetch("""
        SELECT
            tc.table_name,
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.table_schema = 'public'
        ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position;
    """)
    constraints_by_table = {}
    for cr in constraints_res:
        t = cr['table_name']
        cname = cr['constraint_name']
        ctype = cr['constraint_type']
        col = cr['column_name']
        ftable = cr['foreign_table_name']
        fcol = cr['foreign_column_name']
        
        if t not in constraints_by_table:
            constraints_by_table[t] = {}
        if cname not in constraints_by_table[t]:
            constraints_by_table[t][cname] = {
                "type": ctype,
                "columns": [],
                "foreign_table": ftable,
                "foreign_column": fcol
            }
        if col not in constraints_by_table[t][cname]["columns"]:
            constraints_by_table[t][cname]["columns"].append(col)

    # 4. Fetch indexes
    indexes_res = await conn.fetch("""
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname;
    """)
    indexes_by_table = {}
    for idx in indexes_res:
        t = idx['tablename']
        if t not in indexes_by_table:
            indexes_by_table[t] = []
        indexes_by_table[t].append(dict(idx))

    await conn.close()

    os.makedirs(output_dir, exist_ok=True)
    md_file = os.path.join(output_dir, f"{prefix}_schema.md")
    sql_file = os.path.join(output_dir, f"{prefix}_schema.sql")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Generate SQL DDL
    sql_lines = []
    sql_lines.append(f"-- =============================================================================")
    sql_lines.append(f"-- Baseline PostgreSQL Schema: {dbname}")
    sql_lines.append(f"-- Host: {host}:{port}")
    sql_lines.append(f"-- Extracted On: {now_str}")
    sql_lines.append(f"-- Total Tables: {len(tables)}")
    sql_lines.append(f"-- =============================================================================\n")
    sql_lines.append("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
    sql_lines.append("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";\n")

    def table_order(tname):
        if tname == 'user_roles': return 0
        if tname == 'users': return 1
        if tname == 'chat_sessions': return 2
        return 10
    
    sorted_tables = sorted(tables, key=lambda x: (table_order(x), x))

    for t in sorted_tables:
        sql_lines.append(f"-- -----------------------------------------------------------------------------")
        sql_lines.append(f"-- Table: {t}")
        sql_lines.append(f"-- -----------------------------------------------------------------------------")
        sql_lines.append(f"CREATE TABLE IF NOT EXISTS {t} (")
        
        col_defs = []
        for c in columns_by_table.get(t, []):
            cname = c['column_name']
            dtype = c['data_type']
            udt = c['udt_name']
            maxlen = c['character_maximum_length']
            nullable = c['is_nullable'] == 'YES'
            default = c['column_default']

            if dtype == 'character varying':
                type_str = f"VARCHAR({maxlen})" if maxlen else "VARCHAR"
            elif dtype == 'ARRAY':
                inner = udt.lstrip('_')
                type_str = f"{inner}[]"
            else:
                type_str = dtype.upper()

            if default and "nextval(" in default:
                if type_str == 'INTEGER':
                    type_str = "SERIAL"
                    default = None
                elif type_str == 'BIGINT':
                    type_str = "BIGSERIAL"
                    default = None

            parts = [f"    {cname} {type_str}"]
            if not nullable:
                parts.append("NOT NULL")
            if default:
                parts.append(f"DEFAULT {default}")
            col_defs.append(" ".join(parts))

        t_constraints = constraints_by_table.get(t, {})
        for cname, cinfo in t_constraints.items():
            if cinfo['type'] == 'PRIMARY KEY':
                cols_joined = ", ".join(dict.fromkeys(cinfo['columns']))
                col_defs.append(f"    CONSTRAINT {cname} PRIMARY KEY ({cols_joined})")

        sql_lines.append(",\n".join(col_defs))
        sql_lines.append(");\n")

        for idx in indexes_by_table.get(t, []):
            idef = idx['indexdef']
            iname = idx['indexname']
            if iname in t_constraints and t_constraints[iname]['type'] == 'PRIMARY KEY':
                continue
            if "CREATE UNIQUE INDEX " in idef:
                idef = idef.replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ")
            elif "CREATE INDEX " in idef:
                idef = idef.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ")
            sql_lines.append(f"{idef};")
        sql_lines.append("")

    with open(sql_file, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines))

    # Generate Markdown documentation
    md_lines = []
    md_lines.append(f"# Database Baseline Schema: `{dbname}`\n")
    md_lines.append(f"**Host:** `{host}:{port}`  ")
    md_lines.append(f"**Database:** `{dbname}`  ")
    md_lines.append(f"**Extracted On:** {now_str}  ")
    md_lines.append(f"**Total Tables:** {len(tables)}  \n")
    md_lines.append("---\n")
    md_lines.append("## Summary of Tables\n")
    md_lines.append("| # | Table Name | Columns | Description |")
    md_lines.append("|---|---|---|---|")
    for idx, t in enumerate(sorted_tables, 1):
        desc = TABLE_DESCRIPTIONS.get(t, f"Data table storing {t.replace('_', ' ')}")
        col_count = len(columns_by_table.get(t, []))
        md_lines.append(f"| {idx} | [`{t}`](#{idx}-{t}) | {col_count} | {desc} |")
    md_lines.append("\n---\n")

    for idx, t in enumerate(sorted_tables, 1):
        desc = TABLE_DESCRIPTIONS.get(t, f"Data table storing {t.replace('_', ' ')}")
        md_lines.append(f"### {idx}. `{t}`")
        md_lines.append(f"*{desc}*\n")
        md_lines.append("| Column | Type | Nullable | Default | Constraints |")
        md_lines.append("|---|---|---|---|---|")

        t_constraints = constraints_by_table.get(t, {})
        for c in columns_by_table.get(t, []):
            cname = c['column_name']
            dtype = c['data_type']
            udt = c['udt_name']
            maxlen = c['character_maximum_length']
            nullable = "Yes" if c['is_nullable'] == 'YES' else "No"
            default = f"`{c['column_default']}`" if c['column_default'] else "-"

            if dtype == 'character varying':
                type_str = f"`varchar({maxlen})`" if maxlen else "`varchar`"
            elif dtype == 'ARRAY':
                inner = udt.lstrip('_')
                type_str = f"`{inner}[]`"
            else:
                type_str = f"`{dtype}`"

            notes = []
            for cname_con, cinfo in t_constraints.items():
                if cname in cinfo['columns']:
                    if cinfo['type'] == 'PRIMARY KEY':
                        notes.append("🔑 PRIMARY KEY")
                    elif cinfo['type'] == 'UNIQUE':
                        notes.append("✨ UNIQUE")
                    elif cinfo['type'] == 'FOREIGN KEY':
                        notes.append(f"🔗 FK ➔ `{cinfo['foreign_table']}.{cinfo['foreign_column']}`")
            notes_str = ", ".join(dict.fromkeys(notes)) if notes else "-"
            md_lines.append(f"| **`{cname}`** | {type_str} | {nullable} | {default} | {notes_str} |")
        md_lines.append("")

        idxs = indexes_by_table.get(t, [])
        if idxs:
            md_lines.append("**Indexes:**")
            for idobj in idxs:
                md_lines.append(f"- `{idobj['indexname']}`: `{idobj['indexdef']}`")
            md_lines.append("")

    with open(md_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"    [OK] Written {md_file}")
    print(f"    [OK] Written {sql_file}")

async def main():
    for target in DATABASE_TARGETS:
        await extract_schema_for_target(target)

if __name__ == '__main__':
    asyncio.run(main())
