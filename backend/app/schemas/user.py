from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from app.core.constants import UserRole

class UserBase(BaseModel):
    full_name: str
    email: EmailStr | None = None
    phone: str
    role: UserRole = UserRole.CITIZEN

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    organization_id: UUID | None = None

    class Config:
        from_attributes = True
