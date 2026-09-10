from fastapi import Depends
from app.database import get_db
from app.core.permissions import get_current_user, RoleChecker
from sqlalchemy.orm import Session
from app.models.user import User

def get_current_active_user(current_user: User = Depends(get_current_user)):
    return current_user
