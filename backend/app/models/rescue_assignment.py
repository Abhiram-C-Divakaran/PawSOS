import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.core.constants import AssignmentStatus

class RescueAssignment(Base):
    __tablename__ = "rescue_assignments"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    rescue_case_id = Column(UUID, ForeignKey("rescue_cases.id"), nullable=False)
    rescuer_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    
    assigned_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    assignment_status = Column(Enum(AssignmentStatus, name="assignment_status_enum"), default=AssignmentStatus.PENDING)
    
    distance_km = Column(Float, nullable=True)
    dispatch_score = Column(Float, nullable=True)

    rescue_case = relationship("RescueCase", back_populates="assignments")
    rescuer = relationship("User", foreign_keys=[rescuer_id])
