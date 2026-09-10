import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.core.constants import RescueStatus

class RescueStatusHistory(Base):
    __tablename__ = "rescue_status_history"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    rescue_case_id = Column(UUID, ForeignKey("rescue_cases.id"), nullable=False)
    
    previous_status = Column(Enum(RescueStatus, name="rescue_status_enum"), nullable=True)
    new_status = Column(Enum(RescueStatus, name="rescue_status_enum"), nullable=False)
    
    changed_by = Column(UUID, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    rescue_case = relationship("RescueCase", back_populates="history")
    user = relationship("User", foreign_keys=[changed_by])
