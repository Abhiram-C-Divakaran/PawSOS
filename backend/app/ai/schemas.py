from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.core.constants import RescuePriority

class AITriageResult(BaseModel):
    """Structured assessment output from a VisionTriageProvider."""
    suggested_priority: RescuePriority
    score: Optional[int] = Field(default=None, ge=0, le=100)
    confidence: float = Field(..., ge=0.0, le=1.0)
    visible_signs: List[str] = Field(default_factory=list)
    explanation: str = Field(default="")
    provider: str = Field(default="disabled")
    model_name: str = Field(default="pawreach-vision-safety")
    model_version: str = Field(default="v1.0")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return round(v, 4)

class HybridFusionResult(BaseModel):
    """Output of combining deterministic rule triage with AI visual urgency assessment."""
    final_priority: RescuePriority
    final_score: int
    final_reasons: List[str]
    source: str # "RULES" or "HYBRID"
    escalated: bool = False
    ai_status: str # "COMPLETED", "SKIPPED", "FAILED", "DISABLED"
