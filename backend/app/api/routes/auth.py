from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
import uuid
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token, RefreshRequest
from app.schemas.user import UserCreate, UserResponse
from app.config import settings
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
from app.core.rate_limiter import limiter

router = APIRouter()

@router.post("/register", response_model=UserResponse)
@limiter.limit("20/minute")
def register(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):
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
        is_verified=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
@limiter.limit("20/minute")
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Treats username as email or phone
    user = db.query(User).filter(
        (User.email == form_data.username) | (User.phone == form_data.username)
    ).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise UnauthorizedException("Incorrect email/phone or password")
    if not user.is_active:
        raise UnauthorizedException("Inactive user")

    user.last_login_at = datetime.utcnow()
    db.commit()

    access_tok = create_access_token(user.id)
    refresh_tok = create_refresh_token(user.id)

    # Set HttpOnly, Secure cookie in production
    is_prod = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="refresh_token",
        value=refresh_tok,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return {
        "access_token": access_tok,
        "refresh_token": refresh_tok,
        "token_type": "bearer",
    }

@router.post("/refresh", response_model=Token)
@limiter.limit("30/minute")
def refresh(
    request: Request,
    response: Response,
    refresh_in: Optional[RefreshRequest] = None,
    db: Session = Depends(get_db)
):
    # Retrieve refresh token from body or from HttpOnly cookie
    raw_token = None
    if refresh_in and refresh_in.refresh_token:
        raw_token = refresh_in.refresh_token
    elif "refresh_token" in request.cookies:
        raw_token = request.cookies.get("refresh_token")

    if not raw_token:
        raise UnauthorizedException("Refresh token missing")

    # Decode and validate refresh token
    payload = decode_token(raw_token)
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

    # Token Rotation: Issue new access AND fresh new refresh token
    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)

    is_prod = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }

@router.post("/logout")
def logout(response: Response):
    """Clear the refresh token cookie on logout."""
    response.delete_cookie(key="refresh_token")
    return {"success": True, "message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user
