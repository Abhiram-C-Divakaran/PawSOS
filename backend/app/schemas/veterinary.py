from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class TreatmentCreate(BaseModel):
    diagnosis: str | None = None
    treatment_notes: str | None = None
    medications: str | None = None
    facility_id: UUID

class TreatmentUpdate(BaseModel):
    diagnosis: str | None = None
    treatment_notes: str | None = None
    medications: str | None = None
    recovery_status: str | None = None
    treatment_completed_at: datetime | None = None
    follow_up_date: datetime | None = None

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
