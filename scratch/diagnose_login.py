import asyncio
import os
import traceback
import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
import asyncpg
from services.auth_service import AuthService
from models.user_models import UserCreate

async def main():
    db_host = os.getenv('DB_HOST')
    db_port = int(os.getenv('DB_PORT', 5432))
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_pass = os.getenv('DB_PASSWORD')
    print(f"Connecting to DB: {db_user}@{db_host}:{db_port}/{db_name}")

    try:
        pool = await asyncpg.create_pool(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass,
            min_size=1,
            max_size=2
        )
        print(" Connected to DB pool successfully.")
    except Exception as e:
        print(" Failed to connect to DB pool:", e)
        traceback.print_exc()
        return

    async with pool.acquire() as conn:
        cols = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'users'
            ORDER BY ordinal_position
        """)
        print("\n=== Remote 'users' table columns ===")
        for c in cols:
            print(f"  {c['column_name']} ({c['data_type']})")

    auth_service = AuthService(pool)
    print("\n=== Testing authenticateDolphin ===")
    dolphin_payload = {
        "UserName": "STU0002",
        "Password": "STU0002",
        "SecurityKey": "FslKviDfp2tH3qeZla00hp"
    }
    dolphin_result = await auth_service.authenticateDolphin(dolphin_payload)
    print("Dolphin result:", dolphin_result)

    if dolphin_result and dolphin_result.get("Status") != "Error":
        email = (dolphin_result.get("EmailId") or "").lower().strip()
        print(f"\nSearching user by email: '{email}'")
        try:
            existing_user = await auth_service.get_user_by_useremail(email)
            print("Existing user found in DB:", existing_user)
        except Exception as e:
            print("Error in get_user_by_useremail:", e)
            traceback.print_exc()

        # Try create or update
        user_data = UserCreate(
            name=dolphin_result.get("FullName"),
            user_name=dolphin_result.get("LoginId"),
            email=email,
            company_name=dolphin_result.get("CompanyName"),
            role=dolphin_result.get("Role"),
            user_type=dolphin_result.get("UserType"),
            ship_name=dolphin_result.get("ShipName"),
            ship_type=dolphin_result.get("ShipType"),
            id_type=dolphin_result.get("IdType"),
            id_country=dolphin_result.get("IdCountry"),
            company_id=dolphin_result.get("CompanyId"),
        )
        print("\nAttempting create or update with user_data:", user_data)
        try:
            if not existing_user:
                print("Creating user...")
                await auth_service.create_user(user_data)
            else:
                print("Updating user...")
                await auth_service.update_user(
                    user_id=existing_user.id,
                    name=user_data.name,
                    user_name=user_data.user_name,
                    company_name=user_data.company_name,
                    role=user_data.role,
                    user_type=user_data.user_type,
                    ship_name=user_data.ship_name,
                    ship_type=user_data.ship_type,
                    id_type=user_data.id_type,
                    id_country=user_data.id_country,
                    company_id=user_data.company_id,
                )
            updated = await auth_service.get_user_by_useremail(email)
            print("Operation succeeded! User is now:", updated)
        except Exception as e:
            print("Error in create/update user:", e)
            traceback.print_exc()

    # Now let's test Redis
    print("\n=== Testing Redis Connection ===")
    from core.redis_client import redis_service
    try:
        await redis_service.set_user_data("test_key", {"test": "val"})
        val = await redis_service.get_user_data("test_key")
        print("Redis test succeeded, val:", val)
    except Exception as e:
        print("Redis test error:", e)
        traceback.print_exc()

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
