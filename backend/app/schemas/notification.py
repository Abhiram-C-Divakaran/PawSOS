from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime

class DeviceTokenCreate(BaseModel):
    token: str
    platform: str = "WEB"
    device_name: Optional[str] = None

class DeviceTokenResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    token: str
    platform: str
    device_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_seen_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    message: str
    rescue_case_id: Optional[uuid.UUID] = None
    data: Optional[str] = None
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    unread_count: int
