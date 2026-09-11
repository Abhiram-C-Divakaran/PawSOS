from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from app.core.constants import RescuerAvailability

class RescuerLocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)

class RescuerAvailabilityUpdate(BaseModel):
    availability_status: RescuerAvailability

class RescuerProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    availability_status: RescuerAvailability
    latitude: float | None = None
    longitude: float | None = None
    vehicle_available: bool = True
    experience_level: str = "Intermediate"
    service_radius_km: float = 10.0
    last_location_update: datetime
    reliability_score: float = 100.0
    organization_id: UUID | None = None

    class Config:
        from_attributes = True
