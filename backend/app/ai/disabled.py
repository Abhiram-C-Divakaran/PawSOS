from typing import Any, Dict
from app.ai.base import VisionTriageProvider, AITriageDisabledException
from app.ai.schemas import AITriageResult
from app.config import settings

class DisabledVisionTriageProvider(VisionTriageProvider):
    """Fallback provider when AI triage is unconfigured or disabled."""
    @property
    def provider_name(self) -> str:
        return "disabled"

    @property
    def model_name(self) -> str:
        return settings.AI_TRIAGE_MODEL_NAME

    @property
    def model_version(self) -> str:
        return settings.AI_TRIAGE_MODEL_VERSION

    def assess(self, image_bytes: bytes, context: Dict[str, Any], timeout: float = 15.0) -> AITriageResult:
        raise AITriageDisabledException("AI visual triage provider is currently disabled.")
