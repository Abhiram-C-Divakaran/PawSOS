import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.device_token import DeviceToken
from app.models.notification import Notification
from app.api.dependencies import get_current_active_user
from app.schemas.notification import (
    DeviceTokenCreate,
    DeviceTokenResponse,
    NotificationResponse,
    NotificationListResponse,
)

router = APIRouter()

@router.post("/devices", response_model=DeviceTokenResponse)
def register_device_token(
    payload: DeviceTokenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Register or update a push device token (FCM), safely deduplicating across users and concurrent requests."""
    now = datetime.now(timezone.utc)
    device = db.query(DeviceToken).filter(DeviceToken.token == payload.token).first()
    if device:
        device.user_id = current_user.id
        device.platform = payload.platform
        device.device_name = payload.device_name
        device.is_active = True
        device.last_seen_at = now
        db.commit()
        db.refresh(device)
        return device

    try:
        with db.begin_nested():
            device = DeviceToken(
                user_id=current_user.id,
                token=payload.token,
                platform=payload.platform,
                device_name=payload.device_name,
                is_active=True,
                last_seen_at=now,
            )
            db.add(device)
            db.flush()
        db.commit()
        db.refresh(device)
        return device
    except IntegrityError:
        device = db.query(DeviceToken).filter(DeviceToken.token == payload.token).first()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Concurrent device token registration conflict",
            )
        device.user_id = current_user.id
        device.platform = payload.platform
        device.device_name = payload.device_name
        device.is_active = True
        device.last_seen_at = now
        db.commit()
        db.refresh(device)
        return device

@router.delete("/devices/inactive/cleanup")
def cleanup_inactive_device_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Purge deactivated or revoked push device tokens for the current user."""
    removed_count = (
        db.query(DeviceToken)
        .filter(DeviceToken.user_id == current_user.id, DeviceToken.is_active == False)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"success": True, "removed_count": removed_count}

@router.delete("/devices/{token:path}")
def unregister_device_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Deactivate or remove a push device token."""
    cleaned_token = (token or "").strip()
    device = (
        db.query(DeviceToken)
        .filter(DeviceToken.token == cleaned_token, DeviceToken.user_id == current_user.id)
        .first()
    )
    if device:
        device.is_active = False
        db.commit()
    return {"success": True, "message": "Device token deactivated"}

@router.get("", response_model=NotificationListResponse)
def list_notifications(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve notifications for current user, sorted newest first."""
    items = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )
    unread_count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read == False)
        .count()
    )
    return NotificationListResponse(items=items, unread_count=unread_count)

@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Mark a specific notification as read."""
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    notif.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notif)
    return notif

@router.patch("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Mark all unread notifications for current user as read."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.is_read == False
    ).update({"is_read": True, "read_at": datetime.now(timezone.utc)}, synchronize_session=False)
    db.commit()
    return {"success": True, "message": "All notifications marked as read"}
