"""Automated test suite for PawReach Phase 2.9 Staging Security, Validation & Infrastructure Verification.
Tests staging credential enforcement, production seeding refusal, staging config boundaries,
storage failure modes, and FCM notification lifecycle.
"""
import os
import uuid
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.config import Settings
from app.models.device_token import DeviceToken
from app.models.user import User
from app.core.constants import UserRole
from scripts.seed_staging import (
    validate_staging_password,
    seed_staging_database,
    INSECURE_PATTERNS,
)


class TestStagingSeedSecurity:
    """Test suite for staging seed script security and policy validation."""

    def test_missing_staging_password_raises_runtime_error(self, monkeypatch):
        monkeypatch.delenv("STAGING_SEED_PASSWORD", raising=False)
        with pytest.raises(RuntimeError, match="STAGING_SEED_PASSWORD environment variable is required"):
            validate_staging_password(None)

    def test_empty_staging_password_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="STAGING_SEED_PASSWORD environment variable is required"):
            validate_staging_password("")

    def test_short_staging_password_raises_value_error(self):
        with pytest.raises(ValueError, match="at least 14 characters"):
            validate_staging_password("ShortPwd123!")

    @pytest.mark.parametrize("bad_pwd", [
        "StagingPass123!45",
        "my_password_is_long_enough",
        "admin1234567890!",
        "changeme_now_please!",
        "pawsos_staging_pass_123",
        "pawreach_staging_pass_123",
        "secret_12345678_code",
    ])
    def test_insecure_pattern_staging_password_rejected(self, bad_pwd):
        with pytest.raises(ValueError, match="insecure or common pattern"):
            validate_staging_password(bad_pwd)

    def test_valid_strong_staging_password_accepted(self):
        valid = "Kx9#mQ2$vL8!zT5_secure"
        assert validate_staging_password(valid) == valid

    def test_seed_staging_refuses_production_environment(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("STAGING_SEED_PASSWORD", "Kx9#mQ2$vL8!zT5_secure")
        with pytest.raises(RuntimeError, match="FATAL: Staging seeding is strictly prohibited in production"):
            seed_staging_database()

    def test_seed_staging_refuses_when_schema_uninitialized(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.setenv("STAGING_SEED_PASSWORD", "Kx9#mQ2$vL8!zT5_secure")

        with patch("scripts.seed_staging.inspect") as mock_inspect:
            mock_inspector = MagicMock()
            mock_inspector.has_table.return_value = False
            mock_inspect.return_value = mock_inspector

            with pytest.raises(RuntimeError, match="Database schema not initialized"):
                seed_staging_database()


class TestStagingConfigurationValidation:
    """Test suite for backend configuration validation in staging environment."""

    def test_staging_rejects_sqlite_database(self):
        with pytest.raises(ValueError, match="SQLite is strictly prohibited"):
            Settings(
                ENVIRONMENT="staging",
                DATABASE_URL="sqlite:///./staging.db",
                JWT_SECRET_KEY="A" * 32,
                CORS_ORIGINS="https://staging.pawreach.org",
                REDIS_URL="redis://localhost:6379/0",
            )

    def test_staging_rejects_weak_or_short_jwt_secret(self):
        with pytest.raises(ValueError, match="Insecure or weak JWT_SECRET_KEY"):
            Settings(
                ENVIRONMENT="staging",
                DATABASE_URL="postgresql://user:pass@localhost:5432/db",
                JWT_SECRET_KEY="too_short_key",
                CORS_ORIGINS="https://staging.pawreach.org",
                REDIS_URL="redis://localhost:6379/0",
            )

    def test_staging_rejects_development_default_jwt_secret(self):
        with pytest.raises(ValueError, match="Insecure or weak JWT_SECRET_KEY"):
            Settings(
                ENVIRONMENT="staging",
                DATABASE_URL="postgresql://user:pass@localhost:5432/db",
                JWT_SECRET_KEY="dev_secret_key_change_in_production_32chars!!",
                CORS_ORIGINS="https://staging.pawreach.org",
                REDIS_URL="redis://localhost:6379/0",
            )

    def test_staging_rejects_wildcard_cors(self):
        with pytest.raises(ValueError, match="Wildcard '\\*' is prohibited"):
            Settings(
                ENVIRONMENT="staging",
                DATABASE_URL="postgresql://user:pass@localhost:5432/db",
                JWT_SECRET_KEY="A" * 32,
                CORS_ORIGINS="*",
                REDIS_URL="redis://localhost:6379/0",
            )

    def test_staging_rejects_empty_cors(self):
        with pytest.raises(ValueError, match="Explicit CORS_ORIGINS must be configured"):
            Settings(
                ENVIRONMENT="staging",
                DATABASE_URL="postgresql://user:pass@localhost:5432/db",
                JWT_SECRET_KEY="A" * 32,
                CORS_ORIGINS="",
                REDIS_URL="redis://localhost:6379/0",
            )

    def test_staging_rejects_missing_redis_url(self):
        with pytest.raises(ValueError, match="A valid REDIS_URL"):
            Settings(
                ENVIRONMENT="staging",
                DATABASE_URL="postgresql://user:pass@localhost:5432/db",
                JWT_SECRET_KEY="A" * 32,
                CORS_ORIGINS="https://staging.pawreach.org",
                REDIS_URL="",
            )

    def test_staging_rejects_missing_s3_credentials_when_s3_enabled(self):
        with pytest.raises(ValueError, match="AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, and S3_BUCKET_NAME"):
            Settings(
                ENVIRONMENT="staging",
                DATABASE_URL="postgresql://user:pass@localhost:5432/db",
                JWT_SECRET_KEY="A" * 32,
                CORS_ORIGINS="https://staging.pawreach.org",
                REDIS_URL="redis://localhost:6379/0",
                STORAGE_PROVIDER="s3",
                AWS_ACCESS_KEY_ID="test_key",
                AWS_SECRET_ACCESS_KEY="",
                AWS_REGION="us-east-1",
                S3_BUCKET_NAME="bucket",
            )

    def test_valid_staging_configuration_succeeds(self):
        s = Settings(
            ENVIRONMENT="staging",
            DATABASE_URL="postgresql://user:pass@localhost:5432/db",
            JWT_SECRET_KEY="ValidStagingSecretKeyWithOver32CharsLong!",
            CORS_ORIGINS="https://staging.pawreach.org,https://admin.staging.pawreach.org",
            REDIS_URL="redis://:staging_redis@redis.internal:6379/0",
            STORAGE_PROVIDER="local",
        )
        assert s.ENVIRONMENT == "staging"


class TestStorageServiceSecurity:
    """Test suite for storage service failure handling and safety."""

    def test_s3_health_check_returns_false_on_client_error(self):
        from app.services.storage_service import S3StorageProvider
        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.head_bucket.side_effect = Exception("Bucket does not exist or Forbidden")
            mock_boto.return_value = mock_s3

            provider = S3StorageProvider()
            assert provider.check_health() is False

    def test_s3_health_check_returns_true_on_success(self):
        from app.services.storage_service import S3StorageProvider
        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.head_bucket.return_value = {}
            mock_boto.return_value = mock_s3

            provider = S3StorageProvider()
            assert provider.check_health() is True


class TestNotificationServiceLifecycle:
    """Test suite for push notification token management and fallback."""

    def test_fcm_unregistered_token_deactivates_device(self, db):
        from app.services.notification_service import NotificationService
        import firebase_admin.messaging as messaging

        # Create test user
        user = User(
            full_name="Notification Test User",
            email=f"fcm_test_{uuid.uuid4().hex[:8]}@example.com",
            phone="+919876540001",
            password_hash="fakehash",
            role=UserRole.RESCUER,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.flush()

        # Add active device token
        device = DeviceToken(
            user_id=user.id,
            token="stale_unregistered_fcm_token_xyz",
            platform="web",
            is_active=True,
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(device)
        db.commit()

        # Simulate FCM UnregisteredError
        with patch("app.services.notification_service._firebase_initialized", True):
            with patch("firebase_admin.messaging.send") as mock_send:
                mock_send.side_effect = messaging.UnregisteredError("Requested entity was not found.")
                NotificationService._send_fcm(
                    db=db,
                    user_id=user.id,
                    title="Dispatch Offer",
                    message="Emergency alert",
                )

        db.refresh(device)
        assert device.is_active is False

    def test_notification_mock_fallback_when_firebase_uninitialized(self, db):
        from app.services.notification_service import NotificationService

        user = User(
            full_name="Fallback User",
            email=f"fallback_{uuid.uuid4().hex[:8]}@example.com",
            phone="+919876540002",
            password_hash="fakehash",
            role=UserRole.CITIZEN,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.commit()

        with patch("app.services.notification_service._firebase_initialized", False):
            notif = NotificationService.notify_user(
                db=db,
                user_id=user.id,
                title="Case Status Update",
                message="Your case has been updated",
                notification_type="CASE_UPDATE",
            )
            assert notif.id is not None
            assert notif.title == "Case Status Update"
