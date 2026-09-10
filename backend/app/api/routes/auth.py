from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token, RefreshRequest
from app.schemas.user import UserCreate, UserResponse
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.core.exceptions import UnauthorizedException, BadRequestException
from app.api.dependencies import get_current_active_user

router = APIRouter()

@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    user_db = db.query(User).filter((User.email == user_in.email) | (User.phone == user_in.phone)).first()
    if user_db:
        raise BadRequestException("User with this email or phone already exists")
    
    new_user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        phone=user_in.phone,
        password_hash=get_password_hash(user_in.password),
        role=user_in.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm uses 'username' and 'password'
    # We will treat 'username' as email or phone
    user = db.query(User).filter((User.email == form_data.username) | (User.phone == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise UnauthorizedException("Incorrect email/phone or password")
    if not user.is_active:
        raise UnauthorizedException("Inactive user")

    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=Token)
def refresh(refresh_in: RefreshRequest, db: Session = Depends(get_db)):
    # Very basic implementation. Real one should verify the refresh token.
    return {
        "access_token": "mock_new_access_token",
        "refresh_token": "mock_new_refresh_token",
        "token_type": "bearer"
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user
