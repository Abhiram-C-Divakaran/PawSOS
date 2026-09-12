from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime
from app.core.constants import RescuePriority, RescueStatus, RescuerAvailability

class NGOOverviewKPIs(BaseModel):
    active_cases: int
    critical_cases: int
    awaiting_responder: int
    responders_en_route: int
    under_treatment: int
    recovering: int
    avg_dispatch_seconds: float
    avg_response_minutes: float
    completion_rate_pct: float
    responder_availability_pct: float
    total_cases: int

class HotspotItem(BaseModel):
    latitude: float
    longitude: float
    area_name: Optional[str] = None
    incident_count: int
    critical_count: int
    top_species: str

class NGOResponderSummary(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    phone: str
    email: Optional[str] = None
    is_active: bool
    availability_status: RescuerAvailability
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    last_location_update: Optional[datetime] = None
    vehicle_available: bool
    experience_level: str
    reliability_score: float
    completed_rescues: int
    total_offers: int
    accepted_offers: int
    acceptance_rate_pct: float
    active_case_number: Optional[str] = None

class NGOResponderStatusUpdate(BaseModel):
    is_active: Optional[bool] = None
    organization_id: Optional[uuid.UUID] = None
    reliability_score: Optional[float] = None

class NGOCaseActionRequest(BaseModel):
    action: str  # re_dispatch, cancel, mark_unresolved, assign_responder, change_facility
    rescuer_id: Optional[uuid.UUID] = None
    veterinary_facility_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None

class AuditLogItem(BaseModel):
    id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    actor_name: Optional[str] = None
    action: str
    entity: str
    entity_id: Optional[uuid.UUID] = None
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
