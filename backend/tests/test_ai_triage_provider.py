import io
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from PIL import Image

from app.ai.base import (
    AITriageDisabledException,
    AITriageException,
    AITriageTimeoutException,
)
from app.ai.disabled import DisabledVisionTriageProvider
from app.ai.factory import get_vision_triage_provider
from app.ai.fusion import HybridTriageFusionEngine
from app.ai.gemini import GeminiVisionTriageProvider
from app.ai.mock import MockVisionTriageProvider
from app.config import settings
from app.core.constants import RescuePriority


def _make_valid_png_bytes() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (4, 4), color=(255, 0, 0))
    img.save(buf, format="PNG")
    return buf.getvalue()


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


def test_factory_returns_gemini_provider_in_staging(monkeypatch):
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "AI_TRIAGE_API_KEY", "test-gemini-key")
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    provider = get_vision_triage_provider()
    assert isinstance(provider, GeminiVisionTriageProvider)
    assert provider.provider_name == "gemini"
    assert provider.is_configured is True


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


def test_gemini_provider_unconfigured_key_raises_disabled():
    provider = GeminiVisionTriageProvider(api_key="")
    assert provider.is_configured is False
    with pytest.raises(AITriageDisabledException):
        provider.assess(_make_valid_png_bytes(), {"species": "Dog"})


def test_gemini_provider_success_and_privacy_isolation():
    provider = GeminiVisionTriageProvider(
        api_key="secret-gemini-api-key-12345",
        model_name="gemini-2.5-flash",
        model_version="v1.2",
    )
    png_bytes = _make_valid_png_bytes()

    gemini_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "suggested_priority": "CRITICAL",
                                    "score": 92,
                                    "confidence": 0.91,
                                    "visible_signs": [
                                        "Collapsed posture on roadway",
                                        "Visible surface bleeding",
                                    ],
                                    "explanation": "Animal appears immobile with visible bleeding requiring immediate dispatch.",
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = gemini_payload

    captured_call = {}

    class DummyClient:
        def __init__(self, timeout=None):
            captured_call["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def post(self, url, headers=None, json=None):
            captured_call["url"] = url
            captured_call["headers"] = headers
            captured_call["json"] = json
            return mock_response

    # Pass sensitive PII/location/IDs in context to verify they are strictly stripped
    unsafe_context = {
        "species": "Dog",
        "reporter_email": "citizen@private.example",
        "reporter_phone": "+919999988888",
        "user_id": "11111111-2222-3333-4444-555555555555",
        "case_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "latitude": 9.981635,
        "longitude": 76.299884,
        "signed_url": "https://s3.private.example/evidence/secret.png?X-Amz-Signature=deadbeef",
    }

    with patch("app.ai.gemini.httpx.Client", DummyClient):
        result = provider.assess(png_bytes, unsafe_context, timeout=12.0)

    assert result.suggested_priority == RescuePriority.CRITICAL
    assert result.score == 92
    assert result.confidence == 0.91
    assert result.provider == "gemini"
    assert result.model_name == "gemini-2.5-flash"
    assert result.model_version == "v1.2"
    assert "Visible surface bleeding" in result.visible_signs

    # Verify API key is in header only, never in URL
    assert "secret-gemini-api-key-12345" not in captured_call["url"]
    assert captured_call["headers"]["x-goog-api-key"] == "secret-gemini-api-key-12345"

    # Verify zero PII, GPS, IDs, or signed URLs in outbound request body
    serialized_body = json.dumps(captured_call["json"])
    assert "citizen@private.example" not in serialized_body
    assert "+919999988888" not in serialized_body
    assert "11111111-2222-3333-4444-555555555555" not in serialized_body
    assert "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" not in serialized_body
    assert "9.981635" not in serialized_body
    assert "76.299884" not in serialized_body
    assert "X-Amz-Signature" not in serialized_body


def test_gemini_provider_timeout_raises_sanitized_timeout_exception():
    provider = GeminiVisionTriageProvider(api_key="super-secret-key-xyz")
    png_bytes = _make_valid_png_bytes()

    class TimeoutClient:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def post(self, url, headers=None, json=None):
            raise httpx.ReadTimeout("Socket read timeout to generativelanguage.googleapis.com")

    with patch("app.ai.gemini.httpx.Client", TimeoutClient):
        with pytest.raises(AITriageTimeoutException) as exc_info:
            provider.assess(png_bytes, {"species": "Cat"}, timeout=5.0)

    assert "super-secret-key-xyz" not in str(exc_info.value)


@pytest.mark.parametrize(
    "bad_payload",
    [
        {"candidates": []},
        {"candidates": [{"content": {"parts": [{"text": "not-valid-json{"}]}}]},
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "suggested_priority": "INVALID_PRIORITY",
                                        "confidence": 0.85,
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        },
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "suggested_priority": "URGENT",
                                        "confidence": 1.5,
                                    }
                                )
                            }
                        ]
                    }
                }
            ]
        },
    ],
)
def test_gemini_provider_malformed_response_raises_sanitized_exception(bad_payload):
    provider = GeminiVisionTriageProvider(api_key="secret-key-abc")
    png_bytes = _make_valid_png_bytes()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = bad_payload

    class MockClient:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def post(self, url, headers=None, json=None):
            return mock_response

    with patch("app.ai.gemini.httpx.Client", MockClient):
        with pytest.raises(AITriageException) as exc_info:
            provider.assess(png_bytes, {"species": "Dog"})

    assert "secret-key-abc" not in str(exc_info.value)


def test_gemini_provider_http_failure_sanitizes_errors_and_hides_api_key():
    provider = GeminiVisionTriageProvider(api_key="secret-api-key-999")
    png_bytes = _make_valid_png_bytes()

    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.text = "Upstream error with key secret-api-key-999"

    class ErrorClient:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def post(self, url, headers=None, json=None):
            return mock_response

    with patch("app.ai.gemini.httpx.Client", ErrorClient):
        with pytest.raises(AITriageException) as exc_info:
            provider.assess(png_bytes, {"species": "Dog"})

    assert "secret-api-key-999" not in str(exc_info.value)
    assert "HTTP 503" in str(exc_info.value)


def test_gemini_provider_low_confidence_and_non_downgrade_fusion():
    provider = GeminiVisionTriageProvider(api_key="test-key")
    png_bytes = _make_valid_png_bytes()

    # 1. Low confidence CRITICAL suggestion does not escalate MODERATE rule priority
    low_conf_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "suggested_priority": "CRITICAL",
                                    "score": 90,
                                    "confidence": 0.45,
                                    "visible_signs": ["Blurry posture"],
                                    "explanation": "Unclear posture due to motion blur.",
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = low_conf_payload

    class LowConfClient:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def post(self, url, headers=None, json=None):
            return mock_response

    with patch("app.ai.gemini.httpx.Client", LowConfClient):
        ai_res = provider.assess(png_bytes, {"species": "Dog"})

    fused_low = HybridTriageFusionEngine.fuse(
        rule_priority=RescuePriority.MODERATE,
        rule_score=45,
        rule_reasons=["Minor limping"],
        ai_result=ai_res,
        min_confidence=0.70,
    )
    assert fused_low.final_priority == RescuePriority.MODERATE
    assert fused_low.escalated is False

    # 2. High confidence GENERAL suggestion NEVER downgrades URGENT rule priority
    downgrade_attempt_payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "suggested_priority": "GENERAL",
                                    "score": 15,
                                    "confidence": 0.96,
                                    "visible_signs": ["Standing calmly"],
                                    "explanation": "No acute external trauma visible in frame.",
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }
    mock_response.json.return_value = downgrade_attempt_payload

    with patch("app.ai.gemini.httpx.Client", LowConfClient):
        ai_res_general = provider.assess(png_bytes, {"species": "Dog"})

    fused_no_downgrade = HybridTriageFusionEngine.fuse(
        rule_priority=RescuePriority.URGENT,
        rule_score=75,
        rule_reasons=["Active bleeding reported"],
        ai_result=ai_res_general,
        min_confidence=0.70,
    )
    assert fused_no_downgrade.final_priority == RescuePriority.URGENT
    assert fused_no_downgrade.escalated is False
