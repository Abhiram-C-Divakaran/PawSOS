import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base

class AdoptionVisit(Base):
    __tablename__ = "adoption_visits"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID, ForeignKey("adoption_applications.id"), nullable=False, index=True)
    scheduled_at = Column(DateTime, nullable=False)
    status = Column(String, default="SCHEDULED", nullable=False, index=True)  # SCHEDULED, COMPLETED, CANCELLED, NO_SHOW
    notes = Column(Text, nullable=True)

    created_by = Column(UUID, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    application = relationship("AdoptionApplication", back_populates="visits")
    creator = relationship("User", foreign_keys=[created_by])
