import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float, ForeignKey, Integer, CheckConstraint
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base

class FosterHome(Base):
    __tablename__ = "foster_homes"
    __table_args__ = (
        CheckConstraint("capacity >= 1", name="check_foster_capacity_positive"),
        CheckConstraint("current_occupancy >= 0", name="check_foster_occupancy_non_negative"),
        CheckConstraint("current_occupancy <= capacity", name="check_foster_occupancy_within_capacity"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    caregiver_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID, ForeignKey("organizations.id"), nullable=True, index=True)
    
    locality = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    capacity = Column(Integer, default=1, nullable=False)
    current_occupancy = Column(Integer, default=0, nullable=False)
    
    accepted_species = Column(String, nullable=True)
    maximum_animal_size = Column(String, nullable=True)
    
    medical_care_supported = Column(Boolean, default=False)
    availability_status = Column(String, default="AVAILABLE", nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    verified_by_user_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    caregiver = relationship("User", foreign_keys=[caregiver_id])
    organization = relationship("Organization", foreign_keys=[organization_id])
    verified_by = relationship("User", foreign_keys=[verified_by_user_id])
    assignments = relationship("FosterAssignment", back_populates="foster_home")
