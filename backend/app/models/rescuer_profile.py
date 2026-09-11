import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Float, ForeignKey
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.core.constants import RescuerAvailability
from app.models.types import PointField

class RescuerProfile(Base):
    __tablename__ = "rescuer_profiles"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    
    availability_status = Column(
        Enum(RescuerAvailability, name="rescuer_availability_enum"),
        default=RescuerAvailability.AVAILABLE,
        nullable=False,
        index=True
    )
    
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    current_location = Column(PointField, nullable=True)
    
    vehicle_available = Column(Boolean, default=True)
    experience_level = Column(String, default="Intermediate")
    service_radius_km = Column(Float, default=10.0)
    
    last_location_update = Column(DateTime, default=datetime.utcnow)
    reliability_score = Column(Float, default=100.0)
    
    organization_id = Column(UUID, ForeignKey("organizations.id"), nullable=True)

    user = relationship("User", back_populates="rescuer_profile")
    organization = relationship("Organization")
