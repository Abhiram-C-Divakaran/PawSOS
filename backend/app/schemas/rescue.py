from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List, Optional
from app.core.constants import RescuePriority, RescueStatus

class RescueCreate(BaseModel):
    species: str | None = None
    description: str | None = None
    latitude: float
    longitude: float
    address_text: str | None = None
    
    # Triage inputs
    bleeding: bool = False
    can_walk: bool = True
    conscious: bool = True
    vehicle_accident: bool = False
    breathing_difficulty: bool = False
    
    image_url: str | None = None

class RescueStatusUpdate(BaseModel):
    status: RescueStatus
    notes: str | None = None
    veterinary_facility_id: UUID | None = None

class AnimalImageResponse(BaseModel):
    id: UUID
    image_url: str
    image_type: str
    created_at: datetime

    class Config:
        from_attributes = True

class AssignedResponderResponse(BaseModel):
    id: UUID
    full_name: str
    assignment_status: str
    accepted_at: datetime | None = None

    class Config:
        from_attributes = True

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
    veterinary_facility_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    distance_km: float | None = None
    dispatch_radius_km: float | None = None
    dispatch_attempt: int | None = None
    images: List[AnimalImageResponse] = []
    assigned_responder: Optional[AssignedResponderResponse] = None

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

class RuleAssessmentDetail(BaseModel):
    priority: RescuePriority
    score: int
    reasons: List[str]

class AIAssessmentDetail(BaseModel):
    status: str
    source: str
    suggested_priority: Optional[RescuePriority] = None
    score: Optional[int] = None
    confidence: Optional[float] = None
    visible_signs: List[str] = []
    explanation: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class TriageDetailResponse(BaseModel):
    case_id: UUID
    case_number: str
    final_priority: RescuePriority
    final_score: int
    final_reason: str
    rule_assessment: RuleAssessmentDetail
    ai_assessment: AIAssessmentDetail
    disclaimer: str = (
        "AI visual triage provides decision-support for rescue dispatch urgency only. "
        "It does not constitute a veterinary medical diagnosis, injury assessment, or treatment prescription."
    )

