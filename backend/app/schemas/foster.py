import uuid
from datetime import datetime
from typing import Optional, List, Union
from pydantic import BaseModel, ConfigDict, Field

class FosterHomeBase(BaseModel):
    locality: Optional[str] = None
    capacity: int = Field(default=1, ge=1)
    accepted_species: Optional[str] = "Dog, Cat"
    maximum_animal_size: Optional[str] = "Medium"
    medical_care_supported: bool = False
    availability_status: str = "AVAILABLE"

class FosterHomeCreate(FosterHomeBase):
    latitude: float
    longitude: float

class FosterHomeUpdate(BaseModel):
    locality: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity: Optional[int] = Field(default=None, ge=1)
    accepted_species: Optional[str] = None
    maximum_animal_size: Optional[str] = None
    medical_care_supported: Optional[bool] = None
    availability_status: Optional[str] = None

class FosterHomePrivateResponse(BaseModel):
    id: uuid.UUID
    caregiver_id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    locality: Optional[str] = None
    latitude: float
    longitude: float
    capacity: int
    current_occupancy: int
    accepted_species: Optional[str] = None
    maximum_animal_size: Optional[str] = None
    medical_care_supported: bool
    availability_status: str
    verified: bool
    verified_at: Optional[datetime] = None
    verified_by_user_id: Optional[uuid.UUID] = None
    caregiver_name: Optional[str] = None
    caregiver_phone: Optional[str] = None
    caregiver_email: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FosterHomeSafeResponse(BaseModel):
    id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    locality: Optional[str] = None
    capacity: int
    current_occupancy: int
    accepted_species: Optional[str] = None
    maximum_animal_size: Optional[str] = None
    medical_care_supported: bool
    availability_status: str
    verified: bool

    model_config = ConfigDict(from_attributes=True)

class FosterAssignmentCreate(BaseModel):
    rescue_case_id: uuid.UUID
    foster_home_id: uuid.UUID
    expected_end_date: Optional[datetime] = None
    notes: Optional[str] = None

class FosterCareUpdateCreate(BaseModel):
    general_notes: Optional[str] = None
    notes: Optional[str] = None
    appetite_status: Optional[str] = "NORMAL"
    activity_status: Optional[str] = "NORMAL"
    mobility_status: Optional[str] = None
    behavioral_notes: Optional[str] = None
    weight_kg: Optional[float] = None
    medication_administered: Optional[Union[str, bool]] = None
    concern_flag: bool = False
    readiness_recommendation: Optional[str] = None

class FosterCareUpdateResponse(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    created_by: uuid.UUID
    created_at: datetime
    general_notes: Optional[str] = None
    notes: Optional[str] = None
    appetite_status: Optional[str] = None
    activity_status: Optional[str] = None
    weight_kg: Optional[float] = None
    medication_administered: Optional[Union[str, bool]] = None
    concern_flag: bool = False
    readiness_recommendation: Optional[str] = None
    author_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class FosterAssignmentResponse(BaseModel):
    id: uuid.UUID
    animal_id: uuid.UUID
    rescue_case_id: Optional[uuid.UUID] = None
    foster_home_id: uuid.UUID
    start_date: Optional[datetime] = None
    expected_end_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    animal_species: Optional[str] = None
    animal_description: Optional[str] = None
    case_number: Optional[str] = None
    foster_home_locality: Optional[str] = None
    caregiver_name: Optional[str] = None
    care_updates: List[FosterCareUpdateResponse] = []

    model_config = ConfigDict(from_attributes=True)

class FosterMatchRequest(BaseModel):
    case_id: uuid.UUID

class FosterMatchCandidate(BaseModel):
    foster_home_id: uuid.UUID
    locality: Optional[str] = None
    capacity: int
    current_occupancy: int
    remaining_capacity: int
    verified: bool
    availability_status: str
    compatible: bool
    match_score: float
    species_match: bool
    medical_support_match: bool
    size_match: bool
    match_reasons: List[str]
