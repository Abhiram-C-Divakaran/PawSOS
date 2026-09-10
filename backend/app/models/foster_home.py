import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float, ForeignKey, Integer
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base

class FosterHome(Base):
    __tablename__ = "foster_homes"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    caregiver_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    capacity = Column(Integer, default=1)
    current_occupancy = Column(Integer, default=0)
    
    accepted_species = Column(String, nullable=True)
    maximum_animal_size = Column(String, nullable=True)
    
    medical_care_supported = Column(Boolean, default=False)
    availability_status = Column(String, default="AVAILABLE")
    verified = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    caregiver = relationship("User", foreign_keys=[caregiver_id])
