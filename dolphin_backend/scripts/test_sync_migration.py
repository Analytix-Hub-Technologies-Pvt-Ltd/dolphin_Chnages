import asyncio
import asyncpg

async def test_migration(host, port, user, password, dbname):
    print(f"Testing sync_migration.sql on {host}:{port}/{dbname} (Dry-run with rollback)...")
    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=dbname, timeout=10
    )
    with open("sql/sync_migration.sql", "r", encoding="utf-8") as f:
        sql = f.read()
        
    tr = conn.transaction()
    await tr.start()
    try:
        await conn.execute(sql)
        print(f"  [SUCCESS] {host}:{port}/{dbname} executed cleanly!")
    except Exception as e:
        print(f"  [ERROR] on {host}:{port}/{dbname}: {e}")
    finally:
        await tr.rollback()
        await conn.close()

async def main():
    await test_migration('127.0.0.1', 5432, 'postgres', 'CompunetPG@123', 'dolphintest')
    await test_migration('192.168.2.75', 5433, 'postgres', '5BPXsrDXPS38Qt0v', 'dolphintest')
    await test_migration('192.168.2.75', 5433, 'postgres', '5BPXsrDXPS38Qt0v', 'dolphindb')

if __name__ == '__main__':
    asyncio.run(main())
