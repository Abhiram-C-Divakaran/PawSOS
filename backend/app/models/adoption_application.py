import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Text, UniqueConstraint
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base

class AdoptionApplication(Base):
    __tablename__ = "adoption_applications"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID, ForeignKey("adoption_listings.id"), nullable=False, index=True)
    applicant_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)

    status = Column(String, default="SUBMITTED", nullable=False, index=True)  # SUBMITTED, UNDER_REVIEW, VISIT_SCHEDULED, APPROVED, REJECTED, WITHDRAWN

    housing_type = Column(String, nullable=True)  # APARTMENT, INDEPENDENT_HOUSE, FARM, OTHER
    owns_or_rents = Column(String, nullable=True)  # OWNS, RENTS
    landlord_permission = Column(Boolean, nullable=True)
    household_size = Column(Integer, nullable=True)
    children_in_household = Column(Boolean, nullable=True)
    existing_pets = Column(Text, nullable=True)
    animal_experience = Column(Text, nullable=True)
    reason_for_adoption = Column(Text, nullable=False)
    care_plan = Column(Text, nullable=True)

    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by_user_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    decision_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    listing = relationship("AdoptionListing", back_populates="applications")
    applicant = relationship("User", foreign_keys=[applicant_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])
    visits = relationship("AdoptionVisit", back_populates="application", cascade="all, delete-orphan", order_by="desc(AdoptionVisit.scheduled_at)")
