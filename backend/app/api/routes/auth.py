import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.refresh_session import RefreshSession
from app.schemas.auth import Token, RefreshRequest
from app.schemas.user import UserCreate, UserResponse
from app.config import settings
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_jti,
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

    access_tok = create_access_token(user.id)
    refresh_tok = create_refresh_token(user.id)

    # Track RefreshSession in database
    payload = decode_token(refresh_tok)
    jti = payload.get("jti") or uuid.uuid4().hex
    token_hash = hash_jti(jti)
    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    session = RefreshSession(
        user_id=user.id,
        token_hash=token_hash,
        device_id=request.headers.get("user-agent", "Unknown Device")[:255],
        created_at=datetime.utcnow(),
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()

    is_prod = settings.ENVIRONMENT in ["production", "staging"]
    response.set_cookie(
        key="refresh_token",
        value=refresh_tok,
        httponly=True,
        secure=is_prod or settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    # Requirement 23: Do not leak refresh token in response body in production
    return {
        "access_token": access_tok,
        "refresh_token": None if is_prod else refresh_tok,
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
    jti = payload.get("jti")
    if not user_id or not jti:
        raise UnauthorizedException("Malformed token payload")

    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError:
        raise UnauthorizedException("Malformed token payload")

    # Verify session in DB and check for revocation
    token_hash = hash_jti(jti)
    session = db.query(RefreshSession).filter(RefreshSession.token_hash == token_hash).first()
    if not session:
        raise UnauthorizedException("Invalid refresh token session")
    if session.revoked_at is not None:
        # Replay attack detected! Invalidate the downstream token chain to prevent compromised token abuse
        if session.replaced_by:
            try:
                db.query(RefreshSession).filter(
                    RefreshSession.id == uuid.UUID(session.replaced_by)
                ).update({"revoked_at": datetime.utcnow()}, synchronize_session=False)
                db.commit()
            except Exception:
                pass
        raise UnauthorizedException("Refresh token has been revoked")
    if session.expires_at < datetime.utcnow():
        raise UnauthorizedException("Refresh token has expired")

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise UnauthorizedException("User no longer exists")
    if not user.is_active:
        raise UnauthorizedException("User account is inactive")

    # Token Rotation: Issue new access AND fresh new refresh token
    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)

    new_payload = decode_token(new_refresh)
    new_jti = new_payload.get("jti") or uuid.uuid4().hex
    new_token_hash = hash_jti(new_jti)
    new_expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    new_session = RefreshSession(
        user_id=user.id,
        token_hash=new_token_hash,
        device_id=request.headers.get("user-agent", "Unknown Device")[:255],
        created_at=datetime.utcnow(),
        expires_at=new_expires_at,
    )
    db.add(new_session)
    db.flush()

    # Revoke old session and link replacement
    session.revoked_at = datetime.utcnow()
    session.replaced_by = str(new_session.id)
    db.commit()

    is_prod = settings.ENVIRONMENT in ["production", "staging"]
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=is_prod or settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return {
        "access_token": new_access,
        "refresh_token": None if is_prod else new_refresh,
        "token_type": "bearer",
    }

@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Revoke current device refresh session and clear cookie."""
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        try:
            payload = decode_token(raw_token)
            jti = payload.get("jti")
            if jti:
                token_hash = hash_jti(jti)
                session = db.query(RefreshSession).filter(RefreshSession.token_hash == token_hash).first()
                if session and session.revoked_at is None:
                    session.revoked_at = datetime.utcnow()
                    db.commit()
        except Exception:
            pass

    response.delete_cookie(key="refresh_token")
    return {"success": True, "message": "Logged out successfully"}

@router.post("/logout-all")
def logout_all(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Revoke all active refresh sessions across all devices for the current user."""
    db.query(RefreshSession).filter(
        RefreshSession.user_id == current_user.id,
        RefreshSession.revoked_at.is_(None)
    ).update({"revoked_at": datetime.utcnow()}, synchronize_session=False)
    db.commit()

    response.delete_cookie(key="refresh_token")
    return {"success": True, "message": "All device sessions revoked successfully"}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user
