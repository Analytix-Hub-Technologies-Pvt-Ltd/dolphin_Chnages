from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    id: str
    name: str
    email: EmailStr | None = None

    role: str | None = None
    company_name: str | None = None
    user_type: str | None = None
    ship_name: str | None = None
    ship_type: str | None = None
    user_name: str | None = None
    id_type: str | None = None
    id_country: str | None = None
    user_bio: str | None = None
    user_courses: str | None = None
    company_id: str | int | None = None
    role_id: int | None = 1

class UserCreate(BaseModel):
    name: str
    email: EmailStr | None = None
    phone_number: str | None = None
    birth_date: date | None = None
    # password: Optional[str] = Field(default=None, min_length=8)
    user_name: str | None = None
    company_name: str | None = None
    role: str | None = None
    user_type: str | None = None
    ship_name: str | None = None
    ship_type: str | None = None
    id_type: str | None =  None
    id_country: str | None = None
    company_id: str | int | None = None
    role_id: int | None = 1

class LoginRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None


class LoginResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr | None = None
    user_role: str | None = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ForgotPasswordResponse(BaseModel):
    status: str
    message: str

class UserListResponse(BaseModel):
    total: int
    users: List[User]

class UpdateUserRoleRequest(BaseModel):
    role_id: int

