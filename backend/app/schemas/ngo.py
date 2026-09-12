from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime
from app.core.constants import RescuePriority, RescueStatus, RescuerAvailability

class NGOOverviewKPIs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    active_cases: int
    critical_cases: int
    urgent_cases: int = 0
    searching_responder_cases: int = 0
    awaiting_responder: int
    responders_en_route: int
    responders_available: int = 0
    responders_assigned: int = 0
    under_treatment: int
    recovering: int
    unresolved_cases: int = 0
    closed_today: int = 0
    avg_dispatch_seconds: float
    average_response_minutes: Optional[float] = None
    avg_completion_minutes: float = 0.0
    completion_rate_pct: float
    responder_availability_pct: float
    total_cases: int
    average_dispatch_latency_seconds: Optional[float] = None
    average_acceptance_latency_seconds: Optional[float] = None
    average_arrival_minutes: Optional[float] = None
    average_rescue_duration_minutes: Optional[float] = None
    average_case_completion_minutes: Optional[float] = None

class ResponseTimeDataPoint(BaseModel):
    date: str
    average_response_minutes: Optional[float] = None
    cases: int

class RescueOutcomesData(BaseModel):
    outcomes: Dict[str, int]
    rescue_success_rate: float
    unresolved_rate: float
    veterinary_handoff_rate: float
    total_cases: int
    active_field_count: int = 0
    rescued_transport_count: int = 0
    medical_care_count: int = 0
    post_care_count: int = 0
    successful_terminal_count: int = 0
    failure_exception_count: int = 0
    failure_count: int = 0

class NGOInsightsData(BaseModel):
    busiest_day: Optional[str] = None
    busiest_time_range: Optional[str] = None
    top_rescue_area: Optional[str] = None
    responder_acceptance_rate_pct: float = 0.0
    avg_dispatch_attempts: float = 1.0
    escalation_rate_pct: float = 0.0

class OrganizationProfile(BaseModel):
    id: uuid.UUID
    name: str
    organization_type: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    operating_region: Optional[str] = None
    description: Optional[str] = None
    responders_count: int = 0
    veterinary_partners_count: int = 0
    created_at: Optional[datetime] = None
    is_active: bool = True

class OrganizationProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    operating_region: Optional[str] = None
    description: Optional[str] = None

class DispatchSettings(BaseModel):
    default_radius_km: float = 5.0
    radius_escalation_levels: List[float] = [5.0, 10.0, 20.0, 40.0]
    offer_expiration_seconds: int = 90
    stale_location_timeout_seconds: int = 1800

class NotificationPreferences(BaseModel):
    critical_rescue_alerts: bool = True
    dispatch_failures: bool = True
    veterinary_updates: bool = True
    case_closures: bool = True

class HotspotItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    latitude: float
    longitude: float
    area_name: Optional[str] = None
    incident_count: int
    critical_count: int
    urgent_count: int = 0
    top_species: str
    average_response_minutes: Optional[float] = None
    average_acceptance_minutes: Optional[float] = None
    average_arrival_minutes: Optional[float] = None

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
