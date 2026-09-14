import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base

class FosterCareUpdate(Base):
    __tablename__ = "foster_care_updates"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    assignment_id = Column(UUID, ForeignKey("foster_assignments.id"), nullable=False, index=True)
    created_by = Column(UUID, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    general_notes = Column(Text, nullable=True)
    appetite_status = Column(String, nullable=True)  # NORMAL, REDUCED, NONE, INCREASED
    activity_status = Column(String, nullable=True)  # NORMAL, LETHARGIC, RESTLESS, HIGH
    weight_kg = Column(Float, nullable=True)
    medication_administered = Column(Text, nullable=True)
    concern_flag = Column(Boolean, default=False, nullable=False)
    readiness_recommendation = Column(String, nullable=True)  # READY_FOR_ADOPTION, READY_FOR_RELEASE, CONTINUE_FOSTER

    assignment = relationship("FosterAssignment", back_populates="care_updates")
    author = relationship("User", foreign_keys=[created_by])
