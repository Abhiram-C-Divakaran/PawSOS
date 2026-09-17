from typing import Any, Dict
from app.ai.base import VisionTriageProvider, AITriageException, AITriageTimeoutException
from app.ai.schemas import AITriageResult
from app.core.constants import RescuePriority
from app.config import settings

class MockVisionTriageProvider(VisionTriageProvider):
    """
    Deterministic Vision Triage Provider for Automated Test Suites ONLY.
    Strictly prohibited in staging and production environments.
    """
    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "pawreach-vision-mock"

    @property
    def model_version(self) -> str:
        return "test-v1.0"

    def assess(self, image_bytes: bytes, context: Dict[str, Any], timeout: float = 15.0) -> AITriageResult:
        mock_delay = context.get("mock_delay", 0)
        if context.get("mock_timeout") or mock_delay > timeout:
            raise AITriageTimeoutException(
                f"Simulated provider timeout for test assertion (delay {mock_delay}s > timeout {timeout}s)."
            )
        if context.get("mock_fail"):
            raise AITriageException("Simulated provider failure for test assertion.")

        suggested = context.get("mock_priority", RescuePriority.URGENT)
        confidence = float(context.get("mock_confidence", 0.88))
        score = context.get("mock_score", 75)
        visible_signs = context.get("mock_visible_signs", ["visible_wound", "swelling"])
        explanation = context.get(
            "mock_explanation",
            "Visible soft tissue injury and limb swelling detected."
        )

        return AITriageResult(
            suggested_priority=suggested,
            score=score,
            confidence=confidence,
            visible_signs=visible_signs,
            explanation=explanation,
            provider=self.provider_name,
            model_name=self.model_name,
            model_version=self.model_version,
        )
