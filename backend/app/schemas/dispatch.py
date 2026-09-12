from pydantic import BaseModel, ConfigDict
from typing import Optional, List
import uuid
from datetime import datetime
from app.core.constants import AssignmentStatus, RescuePriority, RescueStatus

class DispatchRejectRequest(BaseModel):
    reason: Optional[str] = "other"  # too_far, already_busy, vehicle_unavailable, unsafe_conditions, other

class DispatchCaseSummary(BaseModel):
    id: uuid.UUID
    case_number: str
    species: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    address_text: Optional[str] = None
    triage_priority: RescuePriority
    triage_score: int
    triage_reason: Optional[str] = None
    status: RescueStatus
    created_at: datetime
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class DispatchOfferResponse(BaseModel):
    id: uuid.UUID
    rescue_case_id: uuid.UUID
    rescuer_id: uuid.UUID
    assignment_status: AssignmentStatus
    distance_km: Optional[float] = None
    dispatch_score: Optional[float] = None
    offered_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    case: Optional[DispatchCaseSummary] = None

    model_config = ConfigDict(from_attributes=True)
