from typing import Optional

import asyncpg
import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from asyncpg import Pool
from openai import BaseModel

from api.dependencies import get_db_pool
from models.user_models import LoginRequest, LoginResponse, UserCreate, User
from services.auth_service import AuthService
from core.rate_limiter import rate_limit_auth
from loguru import logger
from config import settings
from fastapi import HTTPException, Depends, Request, Response
from core.redis_client import redis_service
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Text
# from database import get_db, Base
import requests
import json

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
router = APIRouter(prefix="/login", tags=["auth"])

@router.get("/debug-db")
async def debug_db(pool: Pool = Depends(get_db_pool)):
    async with pool.acquire() as conn:
        cols = await conn.fetch("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'users'
        """)
    return cols

@router.post("", response_model=LoginResponse)
@router.post("/login1", response_model=LoginResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    pool: Pool = Depends(get_db_pool)
) -> LoginResponse:

    auth_service = AuthService(pool)

    # -------------------------------------------------
    # HELPER: CREATE OR UPDATE USER
    # -------------------------------------------------
    async def create_or_update_user(user_data: UserCreate):

        email = (user_data.email or "").lower().strip()
        if not email:
            raise HTTPException(
                status_code=400,
                detail="Email address is required"
            )

        existing_user = await auth_service.get_user_by_useremail(email)

        # -----------------------------------------
        # CREATE USER
        # -----------------------------------------
        if not existing_user:
            try:
                await auth_service.create_user(user_data)

            except asyncpg.exceptions.UniqueViolationError:
                # Race condition
                pass

            return await auth_service.get_user_by_useremail(email)

        # -----------------------------------------
        # UPDATE EXISTING USER
        # -----------------------------------------
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

        return await auth_service.get_user_by_useremail(email)

    # -------------------------------------------------
    # 1. TOKEN LOGIN
    # -------------------------------------------------
    if payload.token:

        try:
            decoded = jwt.decode(
                payload.token,
                SECRET_KEY,
                algorithms=["HS256"]
            )

            email = (decoded.get("email") or "").lower().strip()
            username = decoded.get("name", "")

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token expired"
            )

        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

        user = await create_or_update_user(
            UserCreate(
                name=username,
                email=email
            )
        )

    # -------------------------------------------------
    # 2. DOLPHIN LOGIN
    # -------------------------------------------------
    else:

        dolphin_payload = {
            "UserName": payload.email,
            "Password": payload.password,
            "SecurityKey": "FslKviDfp2tH3qeZla00hp"
        }

        dolphin_result = await auth_service.authenticateDolphin(
            dolphin_payload
        )

        if (
            not dolphin_result
            or dolphin_result.get("Status") == "Error"
            or not dolphin_result.get("EmailId")
            or not dolphin_result.get("FullName")
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )

        email = (dolphin_result.get("EmailId") or "").lower().strip()

        user = await create_or_update_user(
            UserCreate(
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
        )

    # -------------------------------------------------
    # USER NOT FOUND AFTER CREATE/UPDATE
    # -------------------------------------------------
    if not user:
        raise HTTPException(
            status_code=500,
            detail="Unable to create or fetch user"
        )

    # -------------------------------------------------
    # STORE USER IN REDIS
    # -------------------------------------------------
    user_data = {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "company_name": user.company_name,
        "company_id": user.company_id,
        "user_type": user.user_type,
        "ship_name": user.ship_name,
        "ship_type": user.ship_type,
        "user_courses": user.user_courses
    }

    await redis_service.set_user_data(
        user_id=str(user.id),
        data=user_data
    )

    redis_user = await redis_service.get_user_data(
        str(user.id)
    )

    logger.debug(f"User stored in Redis: {user.id}")

    # -------------------------------------------------
    # RESPONSE
    # -------------------------------------------------
    return LoginResponse(
        user_id=user.id,
        name=user.name,
        email=user.email
    )




@rate_limit_auth
@router.post("/create", response_model=User)
async def create_user(request: Request, payload: UserCreate, pool: Pool = Depends(get_db_pool)) -> User:
    auth_service = AuthService(pool)
    return await auth_service.create_user(payload)

API_URL = "https://cms.marinerskills.com/api/studentcourses"
SECURITY_KEY = "FslKviDfp2tH3qeZla00hp"

@router.post("/usercourses/{user_id}")
async def sync_user_courses(
    user_id: str,
    pool: Pool = Depends(get_db_pool)
):
    async with pool.acquire() as conn:

        # 1. GET USER + USERNAME
        user = await conn.fetchrow(
            "SELECT id, user_name FROM users WHERE id = $1",
            user_id
        )

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not user["user_name"]:
            raise HTTPException(status_code=400, detail="Username not found")

        try:
            # 2. CALL THIRD-PARTY API (USE user_name)
            response = requests.post(
                API_URL,
                json={
                    "UserName": user["user_name"],
                    "SecurityKey": SECURITY_KEY
                },
                timeout=10
            )

            response.raise_for_status()
            courses = response.json()

            # 3. STORE AS TEXT
            await conn.execute(
                """
                UPDATE users
                SET user_courses = $1,
                    updated_at = NOW()
                WHERE id = $2
                """,
                json.dumps(courses),
                user_id
            )

        except requests.RequestException as e:
            raise HTTPException(status_code=400, detail=str(e))

    return {
        "user_id": user_id,
        "username": user["user_name"],  # ✅ optional debug
        "courses_count": len(courses) if isinstance(courses, list) else 1
    }


# -------------------------------------------------
# GET COURSES
# -------------------------------------------------
@router.get("/usercourses/{user_id}")
async def get_user_courses(
    user_id: str,
    pool: Pool = Depends(get_db_pool)
):
    async with pool.acquire() as conn:

        row = await conn.fetchrow(
            "SELECT user_courses FROM users WHERE id = $1",
            user_id
        )

        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        if not row["user_courses"]:
            return {"user_id": user_id, "courses": []}

        return {
            "user_id": user_id,
            "courses": json.loads(row["user_courses"])
        }
    

test_user_store = {}

# --------------------------------------------------
# REQUEST MODEL
# --------------------------------------------------
class TestLoginRequest(BaseModel):
    username: str
    password: str

    role: Optional[str] = None
    ship: Optional[str] = None
    ship_type: Optional[str] = None
    company: Optional[str] = None


class TestChatRequest(BaseModel):
    message: str


# --------------------------------------------------
# MULTIPLE TEST USERS
# --------------------------------------------------

TEST_USERS = {
    "testuser1": {
        "password": "123456",
        "user_id": "101"
    },
    "testuser2": {
        "password": "123456",
        "user_id": "102"
    },
    "testuser3": {
        "password": "123456",
        "user_id": "103"
    },
    "pammu167@gmail.com": {
        "password": "t9H3eK",
        "user_id": "104"
    },
    "nandukvm@hotmail.com": {
        "password": "R2b6Lw",
        "user_id": "105"
    },
    "k.vivekanand@aduacademy.in": {
        "password": "m4Z8xP",
        "user_id": "106"
    },
    "mullothashok@gmail.com": {
        "password": "A7k9Q2",
        "user_id": "107"
    }
}


# --------------------------------------------------
# TEST LOGIN API
# --------------------------------------------------

@router.post("/test-login")
async def test_login(payload: TestLoginRequest):
    """
    Login Examples:

    username = testuser1
    password = 123456
    → user_id auto assigned as 101

    username = testuser2
    password = 123456
    → user_id auto assigned as 102

    username = testuser3
    password = 123456
    → user_id auto assigned as 103
    """

    user = TEST_USERS.get(payload.username)

    if not user or user["password"] != payload.password:
        raise HTTPException(
            status_code=401,
            detail="Invalid test credentials"
        )

    # Auto assign user_id from username + password match
    test_user_store["user"] = {
        "name": payload.username,
        "role": payload.role or "",
        "ship_name": payload.ship or "",
        "ship_type": payload.ship_type or "",
        "company_name": payload.company or "",
        "user_id": user["user_id"]   # automatically assigned
    }

    return {
        "message": "Test login successful",
        "user_profile": test_user_store["user"]
    }




# @router.post("", response_model=LoginResponse)
# @rate_limit_auth
# async def login(
#     request: Request,
#     payload: LoginRequest,
#     response: Response,
#     pool: Pool = Depends(get_db_pool)
# ) -> LoginResponse:

#     auth_service = AuthService(pool)

#     # -------------------------------
#     # 1. THIRD-PARTY AUTH (PRIORITY)
#     # -------------------------------
#     dolphin_payload = {
#         "UserName": payload.email,
#         "Password": payload.password,
#         "SecurityKey": "FslKviDfp2tH3qeZla00hp"
#     }

#     dolphin_result = await auth_service.authenticateDolphin(dolphin_payload)

#     if not dolphin_result or dolphin_result.get("Status") == "Error":
#         raise HTTPException(status_code=401, detail="Invalid credentials")

#     # -------------------------------
#     # 2. LOCAL AUTH (User object)
#     # -------------------------------
#     user = await auth_service.authenticate(payload)  # MUST return User or None

#     if not user:
#         # -------------------------------
#         # 3. AUTO REGISTER
#         # -------------------------------
#         create_payload = UserCreate(
#             name=dolphin_result["FullName"],
#             user_name=dolphin_result["LoginId"],
#             email=dolphin_result["EmailId"],
#             password=payload.password,
#             phone_number=None,
#             birth_date=None
#         )
        
#         await auth_service.create_user(create_payload)
       
#         # re-authenticate to get User
#         user = await auth_service.authenticate(payload)
        
#     # -------------------------------
#     # 4. SET COOKIE
#     # -------------------------------
#     from config import settings
#     is_prod = settings.app_env == "production"

#     response.set_cookie(
#         key="marine_user_id",
#         value=user.id,
#         httponly=True,
#         secure=is_prod,
#         max_age=60 * 60 * 24 * 30,
#         samesite="lax"
#         )
   
#     return LoginResponse(
#         user_id=user.id,
#         name=user.name,
#         email=user.email
#     )
