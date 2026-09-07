import asyncio, os, sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
from models.database import get_pool, close_pool
from services.auth_service import AuthService
from models.user_models import UserCreate

async def main():
    pool = await get_pool()
    auth_service = AuthService(pool)
    
    # Test update existing user with string company_id
    user = await auth_service.get_user_by_useremail("ranjithash07@gmail.com")
    print("Fetched user:", user.email, "company_id:", user.company_id)
    
    await auth_service.update_user(
        user_id=user.id,
        name=user.name,
        user_name=user.user_name,
        company_name=user.company_name,
        role=user.role,
        user_type=user.user_type,
        ship_name=user.ship_name,
        ship_type=user.ship_type,
        id_type=user.id_type,
        id_country=user.id_country,
        company_id="8"
    )
    print("Successfully updated user with company_id='8'!")
    
    updated_user = await auth_service.get_user_by_useremail("ranjithash07@gmail.com")
    print("Updated user:", updated_user.email, "company_id:", updated_user.company_id)
    
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
