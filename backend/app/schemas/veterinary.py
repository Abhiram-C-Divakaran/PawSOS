from pydantic import BaseModel, field_validator
from uuid import UUID
from datetime import datetime
from typing import List, Union, Optional

class VeterinaryFacilityResponse(BaseModel):
    id: UUID
    name: str
    phone: str | None = None
    email: str | None = None
    latitude: float
    longitude: float
    address: str | None = None
    supports_emergency: bool = False
    is_24_hours: bool = False
    is_verified: bool = False

    class Config:
        from_attributes = True

class TreatmentCreate(BaseModel):
    diagnosis: str
    treatment_notes: str
    medications: Optional[Union[str, List[str]]] = None
    facility_id: UUID
    treatment_started_at: Optional[datetime] = None
    follow_up_date: Optional[datetime] = None
    recovery_status: Optional[str] = "In Treatment"

    @field_validator("medications", mode="before")
    @classmethod
    def format_medications(cls, v):
        if isinstance(v, list):
            return ", ".join(str(item).strip() for item in v if str(item).strip())
        return v

class TreatmentUpdate(BaseModel):
    diagnosis: Optional[str] = None
    treatment_notes: Optional[str] = None
    medications: Optional[Union[str, List[str]]] = None
    recovery_status: Optional[str] = None
    treatment_completed_at: Optional[datetime] = None
    follow_up_date: Optional[datetime] = None

    @field_validator("medications", mode="before")
    @classmethod
    def format_medications(cls, v):
        if isinstance(v, list):
            return ", ".join(str(item).strip() for item in v if str(item).strip())
        return v

class TreatmentResponse(BaseModel):
    id: UUID
    rescue_case_id: UUID
    veterinarian_id: UUID
    facility_id: UUID
    diagnosis: str | None = None
    treatment_notes: str | None = None
    medications: str | None = None
    recovery_status: str | None = None
    treatment_started_at: datetime
    treatment_completed_at: datetime | None = None
    follow_up_date: datetime | None = None

    class Config:
        from_attributes = True
