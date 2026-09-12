import uuid
from datetime import datetime
from sqlalchemy import Column, String, JSON, DateTime, ForeignKey
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    actor_id = Column(UUID, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String, nullable=False, index=True)  # REASSIGN, CANCEL, TRANSFER, ACTIVATE, DEACTIVATE, etc.
    entity = Column(String, nullable=False, index=True)  # RESCUE_CASE, RESPONDER, FACILITY, etc.
    entity_id = Column(UUID, nullable=True, index=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    actor = relationship("User", foreign_keys=[actor_id])
