from pydantic import BaseModel, EmailStr
from uuid import UUID

class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"

class TokenData(BaseModel):
    sub: str | None = None
    type: str | None = None

class LoginRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str | None = None
