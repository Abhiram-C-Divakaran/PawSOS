import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Float, ForeignKey, Integer, Text, CheckConstraint
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.core.constants import RescuePriority, RescueStatus
from app.models.types import PointField

class RescueCase(Base):
    __tablename__ = "rescue_cases"
    __table_args__ = (
        CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="check_rescue_lat"),
        CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="check_rescue_lng"),
        CheckConstraint("triage_score IS NULL OR (triage_score >= 0 AND triage_score <= 100)", name="check_rescue_triage_score"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    case_number = Column(String, unique=True, index=True, nullable=False)
    
    animal_id = Column(UUID, ForeignKey("animals.id"), nullable=True)
    reporter_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    
    species = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(PointField, nullable=True)
    address_text = Column(String, nullable=True)

    # Triage Inputs
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

    # Veterinary facility assignment
    veterinary_facility_id = Column(UUID, ForeignKey("veterinary_facilities.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    animal = relationship("Animal", back_populates="rescue_cases")
    reporter = relationship("User", foreign_keys=[reporter_id])
    veterinary_facility = relationship("VeterinaryFacility", foreign_keys=[veterinary_facility_id])
    images = relationship("AnimalImage", back_populates="rescue_case")
    history = relationship("RescueStatusHistory", back_populates="rescue_case")
    assignments = relationship("RescueAssignment", back_populates="rescue_case")
    treatments = relationship("Treatment", back_populates="rescue_case")
