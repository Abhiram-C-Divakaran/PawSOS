from abc import ABC, abstractmethod
from typing import Any, Dict
from app.ai.schemas import AITriageResult

class AITriageException(Exception):
    """Base exception for AI triage processing."""
    pass

class AITriageDisabledException(AITriageException):
    """Raised when AI triage is invoked but disabled."""
    pass

class AITriageTimeoutException(AITriageException):
    """Raised when an AI provider call times out."""
    pass

class VisionTriageProvider(ABC):
    """
    Abstract interface for pluggable vision triage providers.
    Providers evaluate raw image bytes and return structured urgency recommendations.
    AI assessments are decision-support only and never constitute veterinary diagnoses.
    """
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_version(self) -> str:
        pass

    @abstractmethod
    def assess(self, image_bytes: bytes, context: Dict[str, Any]) -> AITriageResult:
        """
        Assess animal image bytes for urgency signs.
        Context may contain animal species, reported symptoms, or test parameters.
        Must NOT receive sensitive PII (reporter email/phone/name/GPS coordinates).
        """
        pass
