from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token, RefreshRequest
from app.schemas.user import UserCreate, UserResponse
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.constants import UserRole
from app.core.exceptions import UnauthorizedException, BadRequestException
from app.api.dependencies import get_current_active_user

import uuid

router = APIRouter()

@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    user_db = db.query(User).filter(
        (User.email == user_in.email) | (User.phone == user_in.phone)
    ).first()
    if user_db:
        raise BadRequestException("User with this email or phone already exists")
    
    # Public registration ALWAYS assigns CITIZEN role regardless of client inputs
    new_user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        phone=user_in.phone,
        password_hash=get_password_hash(user_in.password),
        role=UserRole.CITIZEN,
        is_active=True,
        is_verified=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Treats username as email or phone
    user = db.query(User).filter(
        (User.email == form_data.username) | (User.phone == form_data.username)
    ).first()
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
    # Decode and validate refresh token
    payload = decode_token(refresh_in.refresh_token)
    
    token_type = payload.get("type")
    if token_type != "refresh":
        raise UnauthorizedException("Invalid token type. Expected refresh token.")
    
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Malformed token payload")
    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError:
        raise UnauthorizedException("Malformed token payload")
        
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise UnauthorizedException("User no longer exists")
    if not user.is_active:
        raise UnauthorizedException("User account is inactive")

    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer"
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user
