"""Test suite for Firebase credential loading from JSON secret or file path,
precedence handling, safe error handling, and REQUIRE_FIREBASE readiness behavior.
"""
import json
import os
from unittest.mock import MagicMock, patch
import pytest

from app.config import Settings, settings
from app.services.notification_service import initialize_firebase_admin


class TestFirebaseCredentialLoading:
    """Test suite covering Firebase configuration methods and precedence."""

    def test_valid_json_secret_initialization(self):
        fake_secret = json.dumps({
            "type": "service_account",
            "project_id": "staging-pawreach",
            "private_key_id": "mock_key_id_123",
            "client_email": "firebase-adminsdk@staging-pawreach.iam.gserviceaccount.com",
        })
        with patch.object(settings, "FIREBASE_CREDENTIALS_JSON", fake_secret):
            with patch.object(settings, "FIREBASE_CREDENTIALS_PATH", ""):
                with patch("firebase_admin.credentials.Certificate") as mock_cert:
                    with patch("firebase_admin.initialize_app") as mock_init:
                        with patch("firebase_admin._apps", {}):
                            success = initialize_firebase_admin()
                            assert success is True
                            mock_cert.assert_called_once()
                            call_args = mock_cert.call_args[0][0]
                            assert call_args["project_id"] == "staging-pawreach"

    def test_invalid_json_secret_fails_gracefully(self):
        corrupted_json = '{"type": "service_account", project_id: bad_syntax'
        with patch.object(settings, "FIREBASE_CREDENTIALS_JSON", corrupted_json):
            with patch.object(settings, "FIREBASE_CREDENTIALS_PATH", ""):
                with patch("firebase_admin._apps", {}):
                    success = initialize_firebase_admin()
                    assert success is False

    def test_valid_path_initialization(self, tmp_path):
        cred_file = tmp_path / "firebase-admin.json"
        cred_file.write_text(json.dumps({"type": "service_account", "project_id": "file-pawreach"}))

        with patch.object(settings, "FIREBASE_CREDENTIALS_JSON", ""):
            with patch.object(settings, "FIREBASE_CREDENTIALS_PATH", str(cred_file)):
                with patch("firebase_admin.credentials.Certificate") as mock_cert:
                    with patch("firebase_admin.initialize_app"):
                        with patch("firebase_admin._apps", {}):
                            success = initialize_firebase_admin()
                            assert success is True
                            mock_cert.assert_called_once_with(str(cred_file))

    def test_missing_path_fails_gracefully(self):
        missing_path = "/nonexistent/path/to/firebase_creds_9999.json"
        with patch.object(settings, "FIREBASE_CREDENTIALS_JSON", ""):
            with patch.object(settings, "FIREBASE_CREDENTIALS_PATH", missing_path):
                with patch("firebase_admin._apps", {}):
                    success = initialize_firebase_admin()
                    assert success is False

    def test_json_takes_precedence_over_path_when_both_configured(self, tmp_path):
        cred_file = tmp_path / "file_creds.json"
        cred_file.write_text(json.dumps({"project_id": "from-file"}))
        json_secret = json.dumps({"project_id": "from-json-secret"})

        with patch.object(settings, "FIREBASE_CREDENTIALS_JSON", json_secret):
            with patch.object(settings, "FIREBASE_CREDENTIALS_PATH", str(cred_file)):
                with patch("firebase_admin.credentials.Certificate") as mock_cert:
                    with patch("firebase_admin.initialize_app"):
                        with patch("firebase_admin._apps", {}):
                            success = initialize_firebase_admin()
                            assert success is True
                            mock_cert.assert_called_once_with({"project_id": "from-json-secret"})

    def test_neither_configured_sets_unconfigured(self):
        with patch.object(settings, "FIREBASE_CREDENTIALS_JSON", ""):
            with patch.object(settings, "FIREBASE_CREDENTIALS_PATH", ""):
                with patch("firebase_admin._apps", {}):
                    success = initialize_firebase_admin()
                    assert success is False


class TestRequireFirebaseBehavior:
    """Test suite covering REQUIRE_FIREBASE configuration validation and readiness probe."""

    def test_staging_config_fails_when_require_firebase_true_and_no_credentials(self):
        with pytest.raises(ValueError, match="REQUIRE_FIREBASE is enabled but neither FIREBASE_CREDENTIALS_JSON nor FIREBASE_CREDENTIALS_PATH"):
            Settings(
                ENVIRONMENT="staging",
                DATABASE_URL="postgresql://user:pass@localhost:5432/db",
                JWT_SECRET_KEY="A" * 32,
                CORS_ORIGINS="https://staging.pawreach.org",
                REDIS_URL="redis://localhost:6379/0",
                REQUIRE_FIREBASE=True,
                FIREBASE_CREDENTIALS_JSON="",
                FIREBASE_CREDENTIALS_PATH="",
            )

    def test_staging_config_succeeds_when_require_firebase_false_and_no_credentials(self):
        s = Settings(
            ENVIRONMENT="staging",
            DATABASE_URL="postgresql://user:pass@localhost:5432/db",
            JWT_SECRET_KEY="A" * 32,
            CORS_ORIGINS="https://staging.pawreach.org",
            REDIS_URL="redis://localhost:6379/0",
            REQUIRE_FIREBASE=False,
            FIREBASE_CREDENTIALS_JSON="",
            FIREBASE_CREDENTIALS_PATH="",
        )
        assert s.REQUIRE_FIREBASE is False

    def test_readiness_probe_degraded_when_require_firebase_true_and_uninitialized(self, client):
        with patch("app.services.notification_service._firebase_initialized", False):
            with patch.object(settings, "REQUIRE_FIREBASE", True):
                with patch.object(settings, "ENVIRONMENT", "staging"):
                    resp = client.get("/api/v1/health/ready")
                    assert resp.status_code == 503
                    data = resp.json()
                    assert data["status"] == "degraded"
                    assert data["services"]["firebase"] == "unavailable"

    def test_readiness_probe_ready_when_require_firebase_false_and_uninitialized(self, client):
        with patch("app.services.notification_service._firebase_initialized", False):
            with patch.object(settings, "REQUIRE_FIREBASE", False):
                with patch.object(settings, "ENVIRONMENT", "development"):
                    resp = client.get("/api/v1/health/ready")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["status"] == "ready"
                    assert data["services"]["firebase"] == "unconfigured"
