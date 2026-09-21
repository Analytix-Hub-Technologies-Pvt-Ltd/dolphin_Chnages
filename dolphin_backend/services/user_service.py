from typing import List, Optional, Tuple
from asyncpg import Pool
from loguru import logger

from models.user_models import User


class UserService:
    def __init__(self, pool: Pool) -> None:
        self.pool = pool

    async def is_super_admin(self, user_id: str) -> bool:
        """Check if a user has the SUPER_ADMIN role."""
        query = """
            SELECT ur.role_name
            FROM users u
            JOIN user_roles ur ON u.role_id = ur.id
            WHERE u.id = $1
        """
        async with self.pool.acquire() as conn:
            role_name = await conn.fetchval(query, user_id)
        
        return role_name == 'SUPER_ADMIN'

    async def get_users(
        self, limit: int, offset: int, search: Optional[str] = None
    ) -> Tuple[int, List[User]]:
        """
        Fetch a list of users with pagination and optional search filter.
        Search matches name, email, or phone_number.
        """
        base_query = "FROM users"
        conditions = []
        params = []

        if search:
            conditions.append("(name ILIKE $1 OR email ILIKE $1 OR phone_number ILIKE $1)")
            params.append(f"%{search}%")

        where_clause = ""
        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)

        count_query = f"SELECT COUNT(*) {base_query} {where_clause}"
        
        # Determine the param index for limit and offset
        limit_idx = len(params) + 1
        offset_idx = len(params) + 2
        
        data_query = f"""
            SELECT * {base_query} {where_clause}
            ORDER BY created_at DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """

        async with self.pool.acquire() as conn:
            total = await conn.fetchval(count_query, *params)
            
            # Execute data query
            params.extend([limit, offset])
            records = await conn.fetch(data_query, *params)

        users = [User(**dict(r)) for r in records]
        return total, users

    async def update_user_role(self, user_id: str, role_id: int) -> Optional[User]:
        """Update the role_id of a user and return the updated user."""
        query = """
            UPDATE users
            SET role_id = $2, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            RETURNING *
        """
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(query, user_id, role_id)

        if record:
            return User(**dict(record))
        return None
