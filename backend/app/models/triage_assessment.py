import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, Float, ForeignKey, Integer, Text, Index, UniqueConstraint
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.core.constants import RescuePriority

class TriageAssessment(Base):
    """
    Auditable record of triage evaluations (Rule-based, Image AI, or Hybrid Fusion).
    Stores provenance, confidence, detected visual signs, and execution metadata.
    Does not replace veterinary medical diagnosis.
    """
    __tablename__ = "triage_assessments"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    rescue_case_id = Column(UUID, ForeignKey("rescue_cases.id", ondelete="CASCADE"), nullable=False, index=True)
    animal_image_id = Column(UUID, ForeignKey("animal_images.id", ondelete="SET NULL"), nullable=True, index=True)

    # Source & Execution Status
    source = Column(String(32), nullable=False, default="IMAGE_AI") # RULES, IMAGE_AI, HYBRID
    status = Column(String(32), nullable=False, default="PENDING", index=True) # PENDING, COMPLETED, FAILED, SKIPPED

    # Urgency Output
    suggested_priority = Column(Enum(RescuePriority, name="rescue_priority_enum"), nullable=True)
    score = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)

    # Structured & Human-readable Explanation
    visible_signs = Column(Text, nullable=True) # JSON-encoded list of detected visual signs
    reason_codes = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)

    # Provider & Model Provenance
    provider = Column(String(64), nullable=False, default="disabled") # disabled, mock (future: external vision provider)
    model_name = Column(String(128), nullable=False, default="pawreach-vision-safety")
    model_version = Column(String(64), nullable=False, default="v1.0")
    sanitized_error_code = Column(String(64), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    rescue_case = relationship("RescueCase", back_populates="triage_assessments")
    animal_image = relationship("AnimalImage")

    __table_args__ = (
        UniqueConstraint(
            "rescue_case_id", "model_name", "model_version",
            name="uq_triage_assessment_case_model",
        ),
        Index("ix_triage_assessment_idempotency", "rescue_case_id", "model_name", "model_version"),
    )
