from typing import List
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
import jwt
import uuid
from sqlalchemy.orm import Session
from app.config import settings
from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.core.constants import UserRole
from app.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_user_id(token: str = Depends(oauth2_scheme)) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        token_type = payload.get("type")
        if token_type != "access":
            raise UnauthorizedException("Invalid token type")
        
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise UnauthorizedException("Could not validate credentials")
        return uuid.UUID(str(user_id_str))
    except (jwt.PyJWTError, ValueError):
        raise UnauthorizedException("Could not validate credentials")

def get_current_user(user_id: uuid.UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    from app.models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UnauthorizedException("User not found")
    if not user.is_active:
        raise ForbiddenException("Inactive user")
    return user

class RoleChecker:
    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, user = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise ForbiddenException("Operation not permitted")
        return user
