from app.ai.base import VisionTriageProvider
from app.ai.disabled import DisabledVisionTriageProvider
from app.ai.mock import MockVisionTriageProvider
from app.config import settings

def get_vision_triage_provider() -> VisionTriageProvider:
    """
    Factory function returning the configured VisionTriageProvider instance.
    Safeguards production and staging by strictly prohibiting Mock providers.
    """
    if not settings.AI_TRIAGE_ENABLED:
        return DisabledVisionTriageProvider()

    provider_name = (settings.AI_TRIAGE_PROVIDER or "disabled").lower().strip()

    if provider_name == "disabled":
        return DisabledVisionTriageProvider()

    if provider_name == "mock":
        env = (settings.ENVIRONMENT or "development").lower()
        if env in ["production", "staging"]:
            raise RuntimeError(
                f"FATAL: Mock AI vision provider is strictly prohibited in {env} environment."
            )
        return MockVisionTriageProvider()

    raise ValueError(f"Unknown AI triage provider: '{provider_name}'. Supported providers: disabled, mock.")
