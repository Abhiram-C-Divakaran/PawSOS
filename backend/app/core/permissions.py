from typing import List
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session
from app.config import settings
from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.core.constants import UserRole
from app.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        token_type = payload.get("type")
        if token_type != "access":
            raise UnauthorizedException("Invalid token type")
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise UnauthorizedException("Could not validate credentials")
        return user_id
    except jwt.PyJWTError:
        raise UnauthorizedException("Could not validate credentials")

# We will need the User model to fetch current user's role. We'll import it conditionally or inside the dep
# to avoid circular imports.
def get_current_user(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
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
