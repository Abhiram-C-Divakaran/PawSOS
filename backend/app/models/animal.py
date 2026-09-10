import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base

class Animal(Base):
    __tablename__ = "animals"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    species = Column(String, nullable=True)
    sex = Column(String, nullable=True)
    approx_age = Column(String, nullable=True)
    colour = Column(String, nullable=True)
    description = Column(String, nullable=True)
    identifying_marks = Column(String, nullable=True)
    
    sterilization_status = Column(String, nullable=True) # Unknown, Spayed, Neutered
    vaccination_status = Column(String, nullable=True)
    
    usual_latitude = Column(Float, nullable=True)
    usual_longitude = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = relationship("AnimalImage", back_populates="animal")
    rescue_cases = relationship("RescueCase", back_populates="animal")
