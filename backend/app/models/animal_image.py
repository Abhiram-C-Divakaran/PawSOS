import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base

class AnimalImage(Base):
    __tablename__ = "animal_images"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    animal_id = Column(UUID, ForeignKey("animals.id"), nullable=True)
    rescue_case_id = Column(UUID, ForeignKey("rescue_cases.id"), nullable=True)
    
    image_url = Column(String, nullable=False)
    image_type = Column(String, nullable=False) # e.g., REPORT, RESCUE, TREATMENT, PROFILE
    uploaded_by = Column(UUID, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    animal = relationship("Animal", back_populates="images")
    rescue_case = relationship("RescueCase", back_populates="images")
