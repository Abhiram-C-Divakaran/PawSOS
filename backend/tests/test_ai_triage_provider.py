import pytest
from app.ai.base import AITriageDisabledException
from app.ai.disabled import DisabledVisionTriageProvider
from app.ai.mock import MockVisionTriageProvider
from app.ai.factory import get_vision_triage_provider
from app.config import settings

def test_disabled_vision_triage_provider():
    provider = DisabledVisionTriageProvider()
    assert provider.provider_name == "disabled"
    with pytest.raises(AITriageDisabledException):
        provider.assess(b"dummy_bytes", {})

def test_mock_vision_triage_provider():
    provider = MockVisionTriageProvider()
    assert provider.provider_name == "mock"
    result = provider.assess(b"image_bytes", {"species": "Dog"})
    assert result.suggested_priority is not None
    assert result.confidence >= 0.70
    assert len(result.visible_signs) > 0
    assert result.explanation is not None

def test_factory_returns_disabled_provider(monkeypatch):
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "disabled")
    provider = get_vision_triage_provider()
    assert isinstance(provider, DisabledVisionTriageProvider)

def test_factory_returns_mock_provider_in_dev_test(monkeypatch):
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    provider = get_vision_triage_provider()
    assert isinstance(provider, MockVisionTriageProvider)

def test_factory_blocks_mock_in_production(monkeypatch):
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(RuntimeError) as exc_info:
        get_vision_triage_provider()
    assert "strictly prohibited" in str(exc_info.value)

def test_factory_blocks_mock_in_staging(monkeypatch):
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    with pytest.raises(RuntimeError) as exc_info:
        get_vision_triage_provider()
    assert "strictly prohibited" in str(exc_info.value)

def test_factory_unknown_provider_raises_error(monkeypatch):
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "non_existent_provider_xyz")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    with pytest.raises(ValueError) as exc_info:
        get_vision_triage_provider()
    assert "Unknown AI triage provider" in str(exc_info.value)
