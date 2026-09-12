import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Float
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.core.constants import OrganizationType

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    organization_type = Column(Enum(OrganizationType, name="organization_type_enum"), nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    
    # Simple float lat/lng for now, PostGIS points can be added if needed for orgs
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    operating_region = Column(String, nullable=True)
    description = Column(String, nullable=True)
    
    verification_status = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="organization")
