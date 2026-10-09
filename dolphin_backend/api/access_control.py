"""Verified caller identity and database-backed administrative access."""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request

from config import settings
from api.dependencies import get_db_pool


def token_secret():
    if len(settings.access_token_secret) < 32:
        raise HTTPException(503, "Configure ACCESS_TOKEN_SECRET with at least 32 random characters")
    return settings.access_token_secret


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now,
                       "exp": now + timedelta(hours=8),
                       "aud": "dolphin-api", "iss": "dolphin-api"},
                      token_secret(), algorithm="HS256")


async def get_current_user(request: Request, pool=Depends(get_db_pool)):
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Bearer access token required", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = jwt.decode(token, token_secret(), algorithms=["HS256"],
                            audience="dolphin-api", issuer="dolphin-api",
                            options={"require": ["sub", "exp", "iat", "aud", "iss"]})
        if not isinstance(claims["sub"], str) or not claims["sub"]:
            raise jwt.InvalidTokenError()
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid or expired access token")
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT u.id, u.email, ur.role_name FROM users u "
                                   "LEFT JOIN user_roles ur ON ur.id = u.role_id WHERE u.id = $1", claims["sub"])
    if not user:
        raise HTTPException(401, "User no longer exists")
    return dict(user)


def can_view_all_sessions(user) -> bool:
    return user.get("role_name") in {"ADMIN", "SUPER_ADMIN"}


async def require_session_admin(user=Depends(get_current_user)):
    if not can_view_all_sessions(user):
        raise HTTPException(403, "ADMIN or SUPER_ADMIN role required")
    return user


async def require_super_admin(user=Depends(get_current_user)):
    if user.get("role_name") != "SUPER_ADMIN":
        raise HTTPException(403, "SUPER_ADMIN role required")
    return user


def session_scope(user, user_id=None, all_users=False):
    """Return an explicit owner filter, or None after privileged authorization."""
    if all_users:
        if user_id is not None:
            raise HTTPException(400, "Use either user_id or all_users, not both")
        if not can_view_all_sessions(user):
            raise HTTPException(403, "ADMIN or SUPER_ADMIN role required")
        return None
    if user_id is not None and not user_id.strip():
        raise HTTPException(400, "user_id must not be empty")
    if user_id is not None and user_id != str(user["id"]) and not can_view_all_sessions(user):
        raise HTTPException(403, "Cannot access another user's sessions")
    return user_id if user_id is not None else str(user["id"])
