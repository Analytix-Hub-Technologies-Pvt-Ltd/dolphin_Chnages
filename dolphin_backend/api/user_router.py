from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from asyncpg import Pool

from api.dependencies import get_db_pool
from api.access_control import require_super_admin
from models.user_models import User, UserListResponse, UpdateUserRoleRequest
from services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])

async def verify_super_admin(
    admin_user_id: Optional[str] = None,
    user=Depends(require_super_admin),
):
    if admin_user_id is not None and admin_user_id != str(user["id"]):
        raise HTTPException(403, "admin_user_id must match the authenticated user")
    return str(user["id"])

@router.get("", response_model=UserListResponse)
async def list_users(
    admin_user_id: str = Depends(verify_super_admin),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Search by name, email or phone number"),
    pool: Pool = Depends(get_db_pool)
):
    """
    List all users with pagination and search. 
    Only accessible by SUPER_ADMIN.
    """
    user_service = UserService(pool)
    total, users = await user_service.get_users(limit, offset, search)
    return UserListResponse(total=total, users=users)

@router.put("/{user_id}/role", response_model=User)
async def update_user_role(
    user_id: str,
    payload: UpdateUserRoleRequest,
    admin_user_id: str = Depends(verify_super_admin),
    pool: Pool = Depends(get_db_pool)
):
    """
    Change the role_id of a user.
    Only accessible by SUPER_ADMIN.
    """
    user_service = UserService(pool)
    updated_user = await user_service.update_user_role(user_id, payload.role_id)
    
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return updated_user
