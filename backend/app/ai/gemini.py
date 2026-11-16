import base64
import io
import json
import logging
import re
from typing import Any, Dict, Optional

import httpx
from PIL import Image

from app.ai.base import (
    AITriageDisabledException,
    AITriageException,
    AITriageTimeoutException,
    VisionTriageProvider,
)
from app.ai.schemas import AITriageResult
from app.config import settings
from app.core.constants import RescuePriority

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
ALLOWED_IMAGE_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MAX_IMAGE_PIXELS = 25_000_000

DEFAULT_PRIORITY_SCORES = {
    RescuePriority.CRITICAL: 90,
    RescuePriority.URGENT: 70,
    RescuePriority.MODERATE: 45,
    RescuePriority.GENERAL: 20,
}

NON_DIAGNOSTIC_SYSTEM_INSTRUCTION = (
    "You are an automated, non-diagnostic visual urgency decision-support assistant for animal rescue dispatch. "
    "Evaluate the image strictly for visible emergency urgency indicators to help prioritize field responder routing. "
    "CRITICAL SAFETY RULES:\n"
    "1. Do NOT provide a veterinary medical diagnosis, disease name, clinical prognosis, or medication/treatment plan.\n"
    "2. Base your assessment solely on visible physical cues in the image (e.g., visible bleeding, collapse/immobility, "
    "entanglement, severe trauma, road hazard exposure, or normal posture).\n"
    "3. Respond ONLY with a valid JSON object matching the required schema."
)


class GeminiVisionTriageProvider(VisionTriageProvider):
    """
    Production-grade external vision triage provider backed by Google Gemini Multimodal API over HTTPS.
    Enforces strict privacy boundaries (sends only validated image bytes and sanitized species),
    hard socket timeouts, error sanitization, and non-diagnostic output validation.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        model_version: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        raw_key = api_key if api_key is not None else getattr(settings, "AI_TRIAGE_API_KEY", "")
        self._api_key = (raw_key or "").strip()

        configured_model = (
            model_name if model_name is not None else getattr(settings, "AI_TRIAGE_MODEL_NAME", "")
        ).strip()
        if not configured_model or configured_model == "pawreach-vision-safety":
            self._model_name = DEFAULT_GEMINI_MODEL
        else:
            self._model_name = configured_model

        self._model_version = (
            model_version if model_version is not None else getattr(settings, "AI_TRIAGE_MODEL_VERSION", "v1.0")
        ).strip() or "v1.0"

        raw_base_url = (
            base_url
            if base_url is not None
            else getattr(settings, "AI_TRIAGE_API_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
        )
        self._base_url = (raw_base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    @staticmethod
    def _validate_and_detect_mime(image_bytes: bytes) -> str:
        if not image_bytes or not isinstance(image_bytes, (bytes, bytearray)):
            raise AITriageException("Empty or invalid image byte payload.")

        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                width, height = img.size
                if width * height > MAX_IMAGE_PIXELS:
                    raise AITriageException("Image dimensions exceed maximum safe pixel limit.")
                fmt = (img.format or "").upper()
                img.verify()
        except AITriageException:
            raise
        except Exception:
            raise AITriageException("Unable to decode or verify image bytes for visual triage.")

        mime_type = ALLOWED_IMAGE_FORMATS.get(fmt)
        if not mime_type:
            raise AITriageException("Unsupported image format for visual triage.")
        return mime_type

    @staticmethod
    def _sanitize_species(context: Optional[Dict[str, Any]]) -> str:
        """
        Extract ONLY the non-identifying animal species string.
        Strictly ignores any PII, GPS coordinates, user IDs, case IDs, or URLs.
        """
        if not isinstance(context, dict):
            return "Animal"
        raw_species = str(context.get("species") or "Animal").strip()
        cleaned = re.sub(r"[^a-zA-Z0-9 _-]", "", raw_species)[:32].strip()
        return cleaned or "Animal"

    @staticmethod
    def _extract_json_dict(raw_text: str) -> Dict[str, Any]:
        if not raw_text or not isinstance(raw_text, str):
            raise AITriageException("Empty assessment text from external vision provider.")

        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            parsed = json.loads(cleaned)
        except Exception:
            raise AITriageException("Malformed JSON in external vision provider response.")

        if not isinstance(parsed, dict):
            raise AITriageException("External vision provider response must be a JSON object.")
        return parsed

    def _parse_provider_response(self, payload: Any) -> AITriageResult:
        if not isinstance(payload, dict):
            raise AITriageException("Unexpected non-object payload from external vision provider.")

        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise AITriageException("No assessment candidates returned by external vision provider.")

        first_candidate = candidates[0] if isinstance(candidates[0], dict) else {}
        content = first_candidate.get("content") if isinstance(first_candidate.get("content"), dict) else {}
        parts = content.get("parts") if isinstance(content.get("parts"), list) else []
        if not parts or not isinstance(parts[0], dict) or "text" not in parts[0]:
            raise AITriageException("Missing text part in external vision provider response.")

        parsed = self._extract_json_dict(parts[0].get("text", ""))

        raw_priority = str(parsed.get("suggested_priority") or "").upper().strip()
        try:
            suggested_priority = RescuePriority(raw_priority)
        except ValueError:
            raise AITriageException("Invalid suggested_priority in external vision provider response.")

        raw_confidence = parsed.get("confidence")
        if raw_confidence is None or isinstance(raw_confidence, bool):
            raise AITriageException("Missing confidence score in external vision provider response.")
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            raise AITriageException("Non-numeric confidence score in external vision provider response.")

        if confidence < 0.0 or confidence > 1.0:
            raise AITriageException("Out-of-range confidence score in external vision provider response.")

        raw_score = parsed.get("score")
        if raw_score is None or isinstance(raw_score, bool):
            score = DEFAULT_PRIORITY_SCORES[suggested_priority]
        else:
            try:
                score = max(0, min(100, int(round(float(raw_score)))))
            except (TypeError, ValueError):
                raise AITriageException("Invalid numeric urgency score in external vision provider response.")

        raw_signs = parsed.get("visible_signs", [])
        if not isinstance(raw_signs, list):
            raise AITriageException("Invalid visible_signs list in external vision provider response.")
        visible_signs = [
            str(sign).strip()[:120]
            for sign in raw_signs[:6]
            if isinstance(sign, (str, int, float)) and str(sign).strip()
        ]

        explanation = str(parsed.get("explanation") or "").strip()[:500]
        if not explanation:
            explanation = f"Visual urgency assessment completed ({suggested_priority.value})."

        return AITriageResult(
            suggested_priority=suggested_priority,
            score=score,
            confidence=confidence,
            visible_signs=visible_signs,
            explanation=explanation,
            provider=self.provider_name,
            model_name=self.model_name,
            model_version=self.model_version,
        )

    def assess(self, image_bytes: bytes, context: Dict[str, Any], timeout: float = 15.0) -> AITriageResult:
        if not self.is_configured:
            raise AITriageDisabledException("External vision provider API key is not configured.")

        mime_type = self._validate_and_detect_mime(image_bytes)
        species = self._sanitize_species(context)
        encoded_image = base64.b64encode(image_bytes).decode("ascii")

        effective_timeout = max(1.0, float(timeout or settings.AI_TRIAGE_TIMEOUT_SECONDS or 15.0))
        url = f"{self._base_url}/models/{self.model_name}:generateContent"

        request_body = {
            "systemInstruction": {
                "parts": [{"text": NON_DIAGNOSTIC_SYSTEM_INSTRUCTION}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": encoded_image,
                            }
                        },
                        {
                            "text": (
                                f"Animal species context: {species}. "
                                "Assess visible dispatch urgency only (non-diagnostic). "
                                "Return JSON with keys: suggested_priority (CRITICAL|URGENT|MODERATE|GENERAL), "
                                "score (0-100), confidence (0.0-1.0), visible_signs (string array), "
                                "and explanation (concise non-diagnostic dispatch advisory)."
                            )
                        },
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=httpx.Timeout(effective_timeout)) as client:
                response = client.post(url, headers=headers, json=request_body)
        except httpx.TimeoutException:
            logger.warning("[AI_TRIAGE_GEMINI] Request timed out after %.1fs", effective_timeout)
            raise AITriageTimeoutException("External vision provider timed out.")
        except httpx.HTTPError as exc:
            logger.warning("[AI_TRIAGE_GEMINI] Transport failure: %s", type(exc).__name__)
            raise AITriageException("External vision provider transport error.")
        except Exception as exc:
            logger.warning("[AI_TRIAGE_GEMINI] Unexpected client error: %s", type(exc).__name__)
            raise AITriageException("External vision provider invocation failed.")

        if response.status_code != 200:
            logger.warning("[AI_TRIAGE_GEMINI] Non-200 status from provider: HTTP %s", response.status_code)
            raise AITriageException(f"External vision provider returned HTTP {response.status_code}.")

        try:
            payload = response.json()
        except Exception:
            raise AITriageException("Non-JSON HTTP body returned by external vision provider.")

        return self._parse_provider_response(payload)
