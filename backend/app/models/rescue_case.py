import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Float, ForeignKey, Integer, Text
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.core.constants import RescuePriority, RescueStatus

class RescueCase(Base):
    __tablename__ = "rescue_cases"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    case_number = Column(String, unique=True, index=True, nullable=False)
    
    animal_id = Column(UUID, ForeignKey("animals.id"), nullable=True)
    reporter_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    
    species = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address_text = Column(String, nullable=True)

    # MVP Triage Inputs
    bleeding = Column(Boolean, default=False)
    can_walk = Column(Boolean, default=True)
    conscious = Column(Boolean, default=True)
    vehicle_accident = Column(Boolean, default=False)
    breathing_difficulty = Column(Boolean, default=False)

    # Triage Results
    triage_score = Column(Integer, nullable=True)
    triage_priority = Column(Enum(RescuePriority, name="rescue_priority_enum"), nullable=True)
    triage_reason = Column(Text, nullable=True)

    status = Column(Enum(RescueStatus, name="rescue_status_enum"), default=RescueStatus.REPORTED, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    animal = relationship("Animal", back_populates="rescue_cases")
    reporter = relationship("User", foreign_keys=[reporter_id])
    images = relationship("AnimalImage", back_populates="rescue_case")
    history = relationship("RescueStatusHistory", back_populates="rescue_case")
    assignments = relationship("RescueAssignment", back_populates="rescue_case")
    treatments = relationship("Treatment", back_populates="rescue_case")
