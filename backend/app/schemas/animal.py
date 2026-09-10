from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class AnimalBase(BaseModel):
    species: str | None = None
    sex: str | None = None
    approx_age: str | None = None
    colour: str | None = None
    description: str | None = None
    identifying_marks: str | None = None
    sterilization_status: str | None = None
    vaccination_status: str | None = None
    usual_latitude: float | None = None
    usual_longitude: float | None = None

class AnimalCreate(AnimalBase):
    pass

class AnimalUpdate(AnimalBase):
    pass

class AnimalResponse(AnimalBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
