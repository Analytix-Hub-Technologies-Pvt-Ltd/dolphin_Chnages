#from _future_ import annotations
import httpx
import uuid
from datetime import datetime
from typing import Optional
from config import settings
from asyncpg import Pool
from loguru import logger
# vignesh - from passlib.hash import bcrypt
# parth 
import bcrypt

from models.user_models import User, LoginRequest, LoginResponse, UserCreate


class AuthService:
    def __init__(self, pool: Pool) -> None:
        self.pool = pool
    # async def create_user(self, payload: UserCreate) -> User:
    #     user_id = str(uuid.uuid4())

    #     password_hash = None

    #     # Only hash password if provided
    #     if payload.password:
    #         password_bytes = payload.password.encode("utf-8")[:72]
    #         password_hash = bcrypt.hashpw(
    #             password_bytes,
    #             bcrypt.gensalt()
    #         ).decode("utf-8")

    #     async with self.pool.acquire() as conn:
    #         await conn.execute(
    #             """
    #             INSERT INTO users (id, name, email, phone_number, birth_date, password_hash)
    #             VALUES ($1, $2, $3, $4, $5, $6)
    #             """,
    #             user_id,
    #             payload.name,
    #             payload.email,
    #             payload.phone_number,
    #             payload.birth_date,
    #             password_hash,
    #             # payload.user_name,
    #         )

    #         # fetch fresh row
    #         record = await conn.fetchrow(
    #             "SELECT * FROM users WHERE id = $1",
    #             user_id
    #         )

    #     return User(**dict(record))

    # async def create_user(self, payload: UserCreate) -> User:
    #     user_id = str(uuid.uuid4())

    #     password_hash = None

    #     if payload.password:
    #         password_bytes = payload.password.encode("utf-8")[:72]
    #         password_hash = bcrypt.hashpw(
    #             password_bytes,
    #             bcrypt.gensalt()
    #         ).decode("utf-8")
    #     else:
    #         password_hash = bcrypt.hashpw(
    #             b"default_password",
    #             bcrypt.gensalt()
    #         ).decode("utf-8")

    #     async with self.pool.acquire() as conn:
    #         await conn.execute(
    #             """
    #             INSERT INTO users (
    #                 id,
    #                 name,
    #                 email,
    #                 phone_number,
    #                 birth_date,
    #                 password_hash,
    #                 user_name,
    #                 company_name,
    #                 role,
    #                 user_type,
    #                 ship_name,
    #                 ship_type,
    #                 id_type,
    #                 id_country
    #             )
    #             VALUES (
    #                 $1, $2, $3, $4, $5, $6,
    #                 $7, $8, $9, $10, $11, $12, $13, $14
    #             )
    #             """,
    #             user_id,
    #             payload.name,
    #             payload.email,
    #             payload.phone_number,
    #             payload.birth_date,
    #             password_hash,
    #             payload.user_name,
    #             payload.company_name,
    #             payload.role,
    #             payload.user_type,
    #             payload.ship_name,
    #             payload.ship_type,
    #             payload.id_type,
    #             payload.id_country,
    #         )

    #         record = await conn.fetchrow(
    #             "SELECT * FROM users WHERE id = $1",
    #             user_id
    #         )

    #     return User(**dict(record))

    async def create_user(self, payload: UserCreate) -> User:
        user_id = str(uuid.uuid4())

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (
                    id,
                    name,
                    email,
                    phone_number,
                    birth_date,
                    user_name,
                    company_name,
                    role,
                    user_type,
                    ship_name,
                    ship_type,
                    id_type,
                    id_country,
                    company_id
                )
                VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8, $9, $10,
                    $11, $12, $13, $14
                )
                """,
                user_id,
                payload.name,
                payload.email,
                payload.phone_number,
                payload.birth_date,
                payload.user_name,
                payload.company_name,
                payload.role,
                payload.user_type,
                payload.ship_name,
                payload.ship_type,
                payload.id_type,
                payload.id_country,
                payload.company_id
            )

            record = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id
            )

        return User(**dict(record))
            
    
    async def authenticate(self, payload: LoginRequest) -> User | None:

        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                SELECT *
                FROM public.users
                WHERE email = $1
                OR user_name = $1
                """,
                payload.email,
            )
        if record is None:
            return None
        # If user was created via SSO and has no password
        return User(**dict(record))
    
    async def authenticateDolphin(self, payload: dict):

        url = settings.auth_api_base_url

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            return data
        
    async def get_user_by_useremail(self, email: str):

        query = """
            SELECT *
            FROM public.users
            WHERE email = $1
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, email)

        if not row:
            return None

        return User(**dict(row))

    async def update_user(
        self,
        user_id,
        name=None,
        user_name=None,
        company_name=None,
        role=None,
        user_type=None,
        ship_name=None,
        ship_type=None,
        id_type=None,
        id_country=None,
        company_id=None,
    ):
        query = """
        UPDATE users
        SET
            name = $2,
            user_name = $3,
            company_name = $4,
            role = $5,
            user_type = $6,
            ship_name = $7,
            ship_type = $8,
            id_type = $9,
            id_country = $10,
            company_id = $11,
            updated_at = NOW()
        WHERE id = $1
        """

        async with self.pool.acquire() as conn:
            await conn.execute(
                query,
                user_id,
                name,
                user_name,
                company_name,
                role,
                user_type,
                ship_name,
                ship_type,
                id_type,
                id_country,
                company_id,
            )    