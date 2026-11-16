"""Test suite for Firebase credential loading from JSON secret or file path,
precedence handling, safe error handling, and REQUIRE_FIREBASE readiness behavior.
"""
import json
import os
from unittest.mock import MagicMock, patch
import pytest

from app.config import Settings, settings
from app.core.constants import UserRole
from app.core.security import create_access_token, get_password_hash
from app.models.device_token import DeviceToken
from app.models.user import User
from app.services.notification_service import NotificationService, initialize_firebase_admin


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


class TestDeviceTokenHardening:
    """Tests for FCM device token deduplication, cross-user browser reassignment, and invalid token cleanup."""

    def test_duplicate_and_cross_user_device_token_registration_and_cleanup(self, client, db):
        user_a = User(
            email="fcm.user.a@test.org",
            phone="+919000011111",
            full_name="FCM User A",
            password_hash="dummy_hash_a",
            role=UserRole.CITIZEN,
            is_active=True,
        )
        user_b = User(
            email="fcm.user.b@test.org",
            phone="+919000022222",
            full_name="FCM User B",
            password_hash="dummy_hash_b",
            role=UserRole.RESCUER,
            is_active=True,
        )
        db.add_all([user_a, user_b])
        db.commit()

        headers_a = {"Authorization": f"Bearer {create_access_token(user_a.id)}"}
        headers_b = {"Authorization": f"Bearer {create_access_token(user_b.id)}"}

        # 1. Empty or whitespace token is rejected
        bad_resp = client.post(
            "/api/v1/notifications/devices",
            json={"token": "   ", "platform": "WEB"},
            headers=headers_a,
        )
        assert bad_resp.status_code == 422

        # 2. User A registers token containing colon/slash
        shared_browser_token = "fcm-browser-token:APA91b/test_token_123"
        reg_a1 = client.post(
            "/api/v1/notifications/devices",
            json={"token": shared_browser_token, "platform": "WEB", "device_name": "Chrome"},
            headers=headers_a,
        )
        assert reg_a1.status_code == 200
        assert reg_a1.json()["user_id"] == str(user_a.id)

        # 3. Duplicate registration by User A is idempotent
        reg_a2 = client.post(
            "/api/v1/notifications/devices",
            json={"token": shared_browser_token, "platform": "WEB", "device_name": "Chrome Updated"},
            headers=headers_a,
        )
        assert reg_a2.status_code == 200
        assert reg_a2.json()["id"] == reg_a1.json()["id"]

        # 4. User B logs in on the same browser and registers the same FCM token -> reassigned without IntegrityError
        reg_b = client.post(
            "/api/v1/notifications/devices",
            json={"token": shared_browser_token, "platform": "WEB", "device_name": "Chrome User B"},
            headers=headers_b,
        )
        assert reg_b.status_code == 200
        assert reg_b.json()["user_id"] == str(user_b.id)
        assert reg_b.json()["is_active"] is True

        # 5. User B unregisters the token (with slash in path) and cleans up inactive tokens
        unreg_b = client.delete(
            f"/api/v1/notifications/devices/{shared_browser_token}",
            headers=headers_b,
        )
        assert unreg_b.status_code == 200

        # User A cannot delete User B's inactive token via cleanup
        cleanup_a = client.delete("/api/v1/notifications/devices/inactive/cleanup", headers=headers_a)
        assert cleanup_a.status_code == 200
        assert cleanup_a.json()["removed_count"] == 0

        # User B cleans up their inactive token
        cleanup_b = client.delete("/api/v1/notifications/devices/inactive/cleanup", headers=headers_b)
        assert cleanup_b.status_code == 200
        assert cleanup_b.json()["removed_count"] == 1

    def test_send_fcm_deactivates_invalid_argument_tokens(self, db):
        user = User(
            email="fcm.invalid@test.org",
            phone="+919000033333",
            full_name="FCM Invalid Token User",
            password_hash="dummy_hash_inv",
            role=UserRole.RESCUER,
            is_active=True,
        )
        db.add(user)
        db.commit()

        token_row = DeviceToken(
            user_id=user.id,
            token="malformed-fcm-token-xyz",
            platform="WEB",
            is_active=True,
        )
        db.add(token_row)
        db.commit()

        class InvalidArgumentError(Exception):
            code = "INVALID_ARGUMENT"

        with patch("app.services.notification_service._firebase_initialized", True):
            with patch("app.services.notification_service.messaging") as mock_messaging:
                mock_messaging.UnregisteredError = type("UnregisteredError", (Exception,), {})
                mock_messaging.SenderIdMismatchError = type("SenderIdMismatchError", (Exception,), {})
                mock_messaging.send.side_effect = InvalidArgumentError("The registration token is not a valid FCM registration token")

                NotificationService._send_fcm(db, user.id, "Test Alert", "Body")

        db.refresh(token_row)
        assert token_row.is_active is False

