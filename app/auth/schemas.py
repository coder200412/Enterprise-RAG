"""
Pydantic schemas for auth request/response validation.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ─── Request Schemas ──────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=4)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6)
    role_name: str = Field(default="employee")


class UpdateRoleRequest(BaseModel):
    role_name: str


# ─── Response Schemas ─────────────────────────────────────────────

class RoleResponse(BaseModel):
    id: int
    name: str
    clearance_level: int
    description: str

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    role: RoleResponse
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    query: str
    response_summary: str
    sources_accessed: str
    guardrail_flags: str
    timestamp: datetime

    class Config:
        from_attributes = True
