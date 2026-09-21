from fastapi import APIRouter, Response, Request

from core.rate_limiter import rate_limit_auth

router = APIRouter(prefix="/logout", tags=["auth"])

@rate_limit_auth
@router.post("")
async def logout(request: Request, response: Response) -> dict:
    response.delete_cookie(key="marine_user_id")
    return {"status": "logged_out"}
