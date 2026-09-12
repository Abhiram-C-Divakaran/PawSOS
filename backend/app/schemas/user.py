from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.core.constants import UserRole

class UserCreate(BaseModel):
    full_name: str
    email: str | None = None
    phone: str
    password: str

class UserResponse(BaseModel):
    id: UUID
    full_name: str
    email: str | None = None
    phone: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    organization_id: UUID | None = None

    class Config:
        from_attributes = True
