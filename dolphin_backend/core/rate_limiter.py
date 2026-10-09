from typing import Dict

from slowapi import Limiter
from slowapi.util import get_remote_address

from config import settings

# Create rate limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    storage_uri=settings.rate_limit_storage_url,
    strategy=settings.rate_limit_strategy,
    enabled=settings.enable_rate_limiting,
)

def get_rate_limit_key(request) -> str:
    """
    Custom key function for rate limiting.
    Can be based on user ID, IP, API key, etc.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return str(user_id)

    return get_remote_address(request)

# Rate limit decorators for different endpoints
def rate_limit_auth(func):
    """Rate limiter for authentication endpoints."""
    return limiter.limit(settings.rate_limit_auth, key_func=get_rate_limit_key)(func)

def rate_limit_chat(func):
    """Rate limiter for chat endpoints."""
    return limiter.limit(settings.rate_limit_chat, key_func=get_rate_limit_key)(func)

def rate_limit_api(func):
    """Rate limiter for general API endpoints."""
    return limiter.limit(settings.rate_limit_api, key_func=get_rate_limit_key)(func)


RATE_LIMIT_CONFIG: Dict[str, str] = {
    "/api/v1/auth/login": settings.rate_limit_auth,
    "/api/v1/auth/register": settings.rate_limit_auth,
    "/api/v1/auth/refresh": settings.rate_limit_auth,
    "/api/v1/chat": settings.rate_limit_chat,
    "/api/v1/quiz": settings.rate_limit_api,
    "/api/v1/course-sync": settings.rate_limit_api,
}

def get_rate_limit_for_path(path: str) -> str:
    return RATE_LIMIT_CONFIG.get(path, settings.rate_limit_default)