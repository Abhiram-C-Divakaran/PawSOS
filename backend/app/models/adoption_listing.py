import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base

class AdoptionListing(Base):
    __tablename__ = "adoption_listings"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    animal_id = Column(UUID, ForeignKey("animals.id"), nullable=False, index=True)
    rescue_case_id = Column(UUID, ForeignKey("rescue_cases.id"), nullable=False, index=True)
    organization_id = Column(UUID, ForeignKey("organizations.id"), nullable=False, index=True)

    title = Column(String, nullable=False)
    public_description = Column(Text, nullable=False)
    public_image_url = Column(String, nullable=True)

    status = Column(String, default="DRAFT", nullable=False, index=True)  # DRAFT, PUBLISHED, PAUSED, CLOSED
    published_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    created_by = Column(UUID, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    animal = relationship("Animal")
    rescue_case = relationship("RescueCase")
    organization = relationship("Organization")
    creator = relationship("User", foreign_keys=[created_by])
    applications = relationship("AdoptionApplication", back_populates="listing", cascade="all, delete-orphan")
