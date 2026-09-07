import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()

async def test():
    conn = await asyncpg.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '5432')),
        database=os.getenv('DB_NAME', 'dalphin_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'root')
    )
    try:
        await conn.execute("UPDATE users SET name = $2, company_id = $3 WHERE id = $1", "2fb5c89e-59ee-4793-9e5f-6e6c23504a8a", "Demostudent2 a2", 8)
        print("Update with int 8 succeeded")
    except Exception as e:
        print("Update with int 8 FAILED with exception:", type(e), e)

    try:
        await conn.execute("UPDATE users SET name = $2, company_id = $3 WHERE id = $1", "2fb5c89e-59ee-4793-9e5f-6e6c23504a8a", "Demostudent2 a2", "8")
        print("Update with str 8 succeeded")
    except Exception as e:
        print("Update with str 8 FAILED with exception:", type(e), e)
    await conn.close()

if __name__ == "__main__":
    asyncio.run(test())
