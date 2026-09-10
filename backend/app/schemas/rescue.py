from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.core.constants import RescuePriority, RescueStatus

class RescueCreate(BaseModel):
    species: str | None = None
    description: str | None = None
    latitude: float
    longitude: float
    address_text: str | None = None
    
    # MVP Triage
    bleeding: bool = False
    can_walk: bool = True
    conscious: bool = True
    vehicle_accident: bool = False
    breathing_difficulty: bool = False
    
    image_url: str | None = None

class RescueStatusUpdate(BaseModel):
    status: RescueStatus
    notes: str | None = None

class RescueResponse(BaseModel):
    id: UUID
    case_number: str
    animal_id: UUID | None = None
    reporter_id: UUID
    species: str | None = None
    description: str | None = None
    latitude: float
    longitude: float
    address_text: str | None = None
    
    triage_score: int | None = None
    triage_priority: RescuePriority | None = None
    triage_reason: str | None = None
    
    status: RescueStatus
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    class Config:
        from_attributes = True

class RescueTimelineResponse(BaseModel):
    id: UUID
    previous_status: RescueStatus | None = None
    new_status: RescueStatus
    notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
