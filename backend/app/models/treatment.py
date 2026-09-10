import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base

class Treatment(Base):
    __tablename__ = "treatments"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    rescue_case_id = Column(UUID, ForeignKey("rescue_cases.id"), nullable=False)
    animal_id = Column(UUID, ForeignKey("animals.id"), nullable=True)
    
    veterinarian_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    facility_id = Column(UUID, ForeignKey("veterinary_facilities.id"), nullable=False)
    
    diagnosis = Column(Text, nullable=True)
    treatment_notes = Column(Text, nullable=True)
    medications = Column(Text, nullable=True)
    
    treatment_started_at = Column(DateTime, default=datetime.utcnow)
    treatment_completed_at = Column(DateTime, nullable=True)
    follow_up_date = Column(DateTime, nullable=True)
    
    recovery_status = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rescue_case = relationship("RescueCase", back_populates="treatments")
    veterinarian = relationship("User", foreign_keys=[veterinarian_id])
    facility = relationship("VeterinaryFacility")
