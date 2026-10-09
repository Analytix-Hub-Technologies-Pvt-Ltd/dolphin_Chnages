from typing import Optional
import asyncpg
import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from asyncpg import Pool
from pydantic import BaseModel
from loguru import logger
import requests
import json

from api.dependencies import get_db_pool
from models.user_models import LoginRequest, LoginResponse, UserCreate, User
from services.auth_service import AuthService
from core.rate_limiter import rate_limit_auth
from config import settings
from api.access_control import create_access_token, require_super_admin
from core.redis_client import redis_service

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm

COMPANY_COURSES_API_URL = "https://cms.marinerskills.com/api/companycourses"
COMPANY_COURSES_SECURITY_KEY = "FslKvipEQ3hT2PfdZla00hp"

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
@rate_limit_auth
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
        if not user_data.email:
            raise HTTPException(status_code=400, detail="User email is required")

        email = str(user_data.email).strip().lower()

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
            except Exception as e:
                logger.error(f"Error creating user in DB: {e}")

            user = await auth_service.get_user_by_useremail(email)
            if not user:
                user = User(
                    id=str(user_data.email),
                    name=user_data.name or "User",
                    email=user_data.email,
                    role=user_data.role,
                    company_name=user_data.company_name,
                    user_type=user_data.user_type,
                    ship_name=user_data.ship_name,
                    ship_type=user_data.ship_type,
                    user_name=user_data.user_name,
                    company_id=user_data.company_id,
                    role_id=user_data.role_id,
                )
            return user

        # -----------------------------------------
        # UPDATE EXISTING USER
        # -----------------------------------------
        try:
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
                role_id=existing_user.role_id,
                company_id=user_data.company_id,
            )
        except Exception as e:
            logger.warning(f"Error updating user in DB: {e}")

        user = await auth_service.get_user_by_useremail(email)
        return user or existing_user

    try:
        # -------------------------------------------------
        # 1. TOKEN LOGIN
        # -------------------------------------------------
        if payload.token:
            if len(SECRET_KEY) < 32:
                raise HTTPException(503, "Configure a strong SECRET_KEY for token login")
            try:
                decoded = jwt.decode(
                    payload.token,
                    SECRET_KEY,
                    algorithms=["HS256"]
                )

                email = str(decoded["email"]).strip().lower()
                username = decoded.get("name") or email

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
            if not payload.email or not payload.password:
                raise HTTPException(
                    status_code=400,
                    detail="Email and password are required"
                )

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
            ):
                raise HTTPException(
                    status_code=401,
                    detail="Invalid credentials"
                )

            email = (dolphin_result.get("EmailId") or payload.email or "").strip().lower()
            full_name = dolphin_result.get("FullName") or dolphin_result.get("LoginId") or email or "User"
            login_id = dolphin_result.get("LoginId") or email

            company_id_val = dolphin_result.get("CompanyId")
            company_id_int = None
            if company_id_val is not None and str(company_id_val).strip().isdigit():
                try:
                    company_id_int = int(company_id_val)
                except (ValueError, TypeError):
                    company_id_int = None

            user = await create_or_update_user(
                UserCreate(
                    name=full_name,
                    user_name=login_id,
                    email=email,
                    company_name=dolphin_result.get("CompanyName"),
                    role=dolphin_result.get("Role"),
                    user_type=dolphin_result.get("UserType"),
                    ship_name=dolphin_result.get("ShipName"),
                    ship_type=dolphin_result.get("ShipType"),
                    id_type=dolphin_result.get("IdType"),
                    id_country=dolphin_result.get("IdCountry"),
                    company_id=company_id_int,
                    role_id=1,
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
        # FETCH COMPANY COURSES
        # -------------------------------------------------
        company_courses = []
        company_id_str = str(user.company_id) if user.company_id else None
        if company_id_str:
            try:
                cc_response = requests.get(
                    COMPANY_COURSES_API_URL,
                    json={
                        "CompanyId": company_id_str,
                        "SecurityKey": COMPANY_COURSES_SECURITY_KEY
                    },
                    timeout=10.0
                )
                if cc_response.status_code == 200:
                    cc_data = cc_response.json()
                    company_courses = cc_data.get("courses", [])
            except Exception as e:
                logger.warning(f"Error fetching company courses: {e}")

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
            "user_courses": user.user_courses,
            "company_courses": company_courses
        }

        try:
            await redis_service.set_user_data(
                user_id=str(user.id),
                data=user_data
            )
            redis_user = await redis_service.get_user_data(
                str(user.id)
            )
            logger.info(f"Redis user stored: {redis_user}")
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")

        # -------------------------------------------------
        # FETCH ROLE NAME
        # -------------------------------------------------
        role_name = None
        if user.role_id:
            try:
                async with pool.acquire() as conn:
                    role_record = await conn.fetchrow(
                        "SELECT role_name FROM user_roles WHERE id = $1",
                        user.role_id
                    )
                    if role_record:
                        role_name = role_record["role_name"]
            except Exception as e:
                logger.warning(f"Unable to fetch role name: {e}")

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------
        return LoginResponse(
            access_token=create_access_token(str(user.id)),
            user_id=str(user.id),
            name=user.name,
            email=user.email,
            user_role=role_name,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during login: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Login failed: {str(e)}"
        )




@rate_limit_auth
@router.post("/create", response_model=User, dependencies=[Depends(require_super_admin)])
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
    },
    "ashwathykr009@yahoo.co.in": {
        "password": "k8P2wX",
        "user_id": "108"
    },
    "karthikeyanc@compunetconnections.com": {
        "password": "c4M7vN",
        "user_id": "109"
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
from api.access_control import create_access_token
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
