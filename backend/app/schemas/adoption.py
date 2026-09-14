import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field

class AdoptionListingBase(BaseModel):
    title: str = Field(min_length=3)
    public_description: str = Field(min_length=10)
    public_image_url: Optional[str] = None

class AdoptionListingCreate(AdoptionListingBase):
    rescue_case_id: uuid.UUID

class AdoptionListingUpdate(BaseModel):
    title: Optional[str] = None
    public_description: Optional[str] = None
    public_image_url: Optional[str] = None
    status: Optional[str] = None

class AdoptionListingPublicResponse(BaseModel):
    id: uuid.UUID
    title: str
    public_description: str
    public_image_url: Optional[str] = None
    status: str
    published_at: Optional[datetime] = None
    species: Optional[str] = None
    sex: Optional[str] = None
    approx_age: Optional[str] = None
    colour: Optional[str] = None
    identifying_marks: Optional[str] = None
    sterilization_status: Optional[str] = None
    vaccination_status: Optional[str] = None
    organization_name: Optional[str] = None
    organization_operating_region: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class AdoptionListingInternalResponse(AdoptionListingPublicResponse):
    animal_id: uuid.UUID
    rescue_case_id: uuid.UUID
    organization_id: uuid.UUID
    case_number: Optional[str] = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    applications_count: int = 0
    closed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class AdoptionApplicationCreate(BaseModel):
    housing_type: Optional[str] = "APARTMENT"
    owns_or_rents: Optional[str] = "OWNS"
    landlord_permission: Optional[bool] = None
    household_size: Optional[int] = 1
    children_in_household: Optional[bool] = False
    existing_pets: Optional[str] = None
    animal_experience: Optional[str] = None
    reason_for_adoption: str = Field(min_length=10)
    care_plan: Optional[str] = None

class AdoptionApplicationApplicantResponse(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    status: str
    housing_type: Optional[str] = None
    owns_or_rents: Optional[str] = None
    household_size: Optional[int] = None
    reason_for_adoption: str
    submitted_at: datetime
    listing_title: Optional[str] = None
    animal_species: Optional[str] = None
    public_image_url: Optional[str] = None
    organization_name: Optional[str] = None
    visit_info: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True)

class AdoptionApplicationReviewerResponse(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    applicant_id: uuid.UUID
    applicant_name: Optional[str] = None
    applicant_phone: Optional[str] = None
    applicant_email: Optional[str] = None
    status: str
    housing_type: Optional[str] = None
    owns_or_rents: Optional[str] = None
    landlord_permission: Optional[bool] = None
    household_size: Optional[int] = None
    children_in_household: Optional[bool] = None
    existing_pets: Optional[str] = None
    animal_experience: Optional[str] = None
    reason_for_adoption: str
    care_plan: Optional[str] = None
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by_name: Optional[str] = None
    decision_notes: Optional[str] = None
    visits: List[Any] = []
    listing_title: Optional[str] = None
    animal_species: Optional[str] = None
    case_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class AdoptionVisitCreate(BaseModel):
    scheduled_at: datetime
    notes: Optional[str] = None

class AdoptionVisitUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class AdoptionVisitResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    scheduled_at: datetime
    status: str
    notes: Optional[str] = None
    created_by: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AdoptionDecisionRequest(BaseModel):
    decision_notes: Optional[str] = None
