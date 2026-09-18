import asyncio
import asyncpg

async def get_db_metadata(host, port, user, password, dbname):
    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=dbname, timeout=10
    )
    
    # 1. Tables
    tables_res = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
    """)
    tables = [r['table_name'] for r in tables_res]
    
    # 2. Columns
    cols_res = await conn.fetch("""
        SELECT table_name, column_name, data_type, udt_name, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public';
    """)
    cols = {}
    for c in cols_res:
        t = c['table_name']
        if t not in cols: cols[t] = {}
        cols[t][c['column_name']] = {
            'type': c['data_type'],
            'udt': c['udt_name'],
            'nullable': c['is_nullable'],
            'default': c['column_default']
        }
        
    # 3. Constraints
    cons_res = await conn.fetch("""
        SELECT tc.table_name, tc.constraint_name, tc.constraint_type, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = 'public';
    """)
    cons = {}
    for r in cons_res:
        t = r['table_name']
        if t not in cons: cons[t] = {}
        cname = r['constraint_name']
        if cname not in cons[t]:
            cons[t][cname] = {'type': r['constraint_type'], 'cols': []}
        cons[t][cname]['cols'].append(r['column_name'])
        
    # 4. Row counts
    counts = {}
    for t in tables:
        try:
            cnt = await conn.fetchval(f"SELECT COUNT(*) FROM {t};")
            counts[t] = cnt
        except Exception as e:
            counts[t] = f"Error: {e}"
            
    await conn.close()
    return {
        'tables': set(tables),
        'columns': cols,
        'constraints': cons,
        'counts': counts
    }

async def main():
    local_dt = await get_db_metadata('127.0.0.1', 5432, 'postgres', 'CompunetPG@123', 'dolphintest')
    remote_dt = await get_db_metadata('192.168.2.75', 5433, 'postgres', '5BPXsrDXPS38Qt0v', 'dolphintest')
    remote_db = await get_db_metadata('192.168.2.75', 5433, 'postgres', '5BPXsrDXPS38Qt0v', 'dolphindb')
    
    print("=================================================================")
    print("1. TABLE LEVEL COMPARISON: LOCAL dolphintest vs REMOTE dolphintest")
    print("=================================================================")
    common = local_dt['tables'].intersection(remote_dt['tables'])
    local_only = local_dt['tables'] - remote_dt['tables']
    remote_only = remote_dt['tables'] - local_dt['tables']
    print(f"Common Tables ({len(common)}): {sorted(list(common))}")
    print(f"Local ONLY Tables ({len(local_only)}): {sorted(list(local_only))}")
    print(f"Remote ONLY Tables ({len(remote_only)}): {sorted(list(remote_only))}")
    
    print("\n=================================================================")
    print("2. COLUMN LEVEL DIFFERENCES IN COMMON TABLES")
    print("=================================================================")
    for t in sorted(list(common)):
        l_cols = set(local_dt['columns'].get(t, {}).keys())
        r_cols = set(remote_dt['columns'].get(t, {}).keys())
        if l_cols != r_cols:
            print(f"\nTable: {t}")
            if l_cols - r_cols:
                print(f"  Cols in Local but MISSING in Remote: {l_cols - r_cols}")
            if r_cols - l_cols:
                print(f"  Cols in Remote but MISSING in Local: {r_cols - l_cols}")
        # Check column types/defaults
        for col in l_cols.intersection(r_cols):
            l_info = local_dt['columns'][t][col]
            r_info = remote_dt['columns'][t][col]
            diffs = []
            if l_info['type'] != r_info['type']:
                diffs.append(f"type: local={l_info['type']} vs remote={r_info['type']}")
            if l_info['nullable'] != r_info['nullable']:
                diffs.append(f"nullable: local={l_info['nullable']} vs remote={r_info['nullable']}")
            if diffs:
                print(f"  Col '{col}' difference in '{t}': {', '.join(diffs)}")

    print("\n=================================================================")
    print("3. ROW COUNT COMPARISON (DATA PRESENCE)")
    print("=================================================================")
    all_tables = sorted(list(local_dt['tables'].union(remote_dt['tables']).union(remote_db['tables'])))
    print(f"{'Table':<30} | {'Local dolphintest':<20} | {'Remote dolphintest':<20} | {'Remote dolphindb':<20}")
    print("-" * 100)
    for t in all_tables:
        l_cnt = str(local_dt['counts'].get(t, 'N/A'))
        r_cnt = str(remote_dt['counts'].get(t, 'N/A'))
        db_cnt = str(remote_db['counts'].get(t, 'N/A'))
        print(f"{t:<30} | {l_cnt:<20} | {r_cnt:<20} | {db_cnt:<20}")

    print("\n=================================================================")
    print("4. COMPARISON: REMOTE dolphintest vs REMOTE dolphindb")
    print("=================================================================")
    print(f"dolphindb ONLY vs dolphintest: {remote_db['tables'] - remote_dt['tables']}")
    print(f"dolphintest ONLY vs dolphindb: {remote_dt['tables'] - remote_db['tables']}")

if __name__ == '__main__':
    asyncio.run(main())
