import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base

class FosterAssignment(Base):
    __tablename__ = "foster_assignments"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    animal_id = Column(UUID, ForeignKey("animals.id"), nullable=False)
    rescue_case_id = Column(UUID, ForeignKey("rescue_cases.id"), nullable=True)
    foster_home_id = Column(UUID, ForeignKey("foster_homes.id"), nullable=False)
    
    start_date = Column(DateTime, default=datetime.utcnow)
    expected_end_date = Column(DateTime, nullable=True)
    actual_end_date = Column(DateTime, nullable=True)
    
    status = Column(String, default="ACTIVE")
    notes = Column(Text, nullable=True)

    animal = relationship("Animal")
    rescue_case = relationship("RescueCase")
    foster_home = relationship("FosterHome")
