"""Comprehensive regression tests for Celery worker heartbeat, Redis normalization, and fail-closed readiness."""
import logging
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.tasks.celery_app import celery_app, get_redis_client, normalize_celery_redis_url
from app.tasks.dispatch_tasks import worker_heartbeat_task
from app.main import app


class TestRedisNormalizationAndClient:
    """Verify canonical Redis URL normalization and client helper."""

    def test_get_redis_client_applies_normalization_for_rediss(self):
        """Verify get_redis_client enforces ssl_cert_reqs=required on rediss:// without leaking secrets."""
        secret_url = "rediss://default:supersecret_token_12345@global.upstash.io:6379"
        client = get_redis_client(secret_url)
        conn_kwargs = client.connection_pool.connection_kwargs
        assert conn_kwargs.get("ssl_cert_reqs") == "required"
        assert conn_kwargs.get("host") == "global.upstash.io"
        assert conn_kwargs.get("port") == 6379

    def test_get_redis_client_preserves_plain_redis(self):
        """Verify get_redis_client handles plain redis:// without modifying it."""
        plain_url = "redis://127.0.0.1:6379/0"
        client = get_redis_client(plain_url)
        conn_kwargs = client.connection_pool.connection_kwargs
        assert "ssl_cert_reqs" not in conn_kwargs
        assert conn_kwargs.get("host") == "127.0.0.1"
        assert conn_kwargs.get("port") == 6379


class TestWorkerHeartbeatTask:
    """Verify worker_heartbeat_task behavior, sanitization, and timing."""

    def test_successful_heartbeat_writes_utc_iso_and_ttl(self):
        """Verify worker_heartbeat_task writes ISO UTC timestamp and applies CELERY_HEARTBEAT_TTL_SECONDS."""
        mock_redis = MagicMock()
        with patch("app.tasks.celery_app.get_redis_client", return_value=mock_redis):
            result = worker_heartbeat_task(is_initial=True)

            assert result["status"] == "ok"
            heartbeat_at = result["heartbeat_at"]
            parsed = datetime.fromisoformat(heartbeat_at)
            assert parsed.tzinfo is not None

            # Verify Redis set call
            mock_redis.set.assert_called_once()
            key, val = mock_redis.set.call_args[0]
            kwargs = mock_redis.set.call_args[1]
            assert key == "celery_worker_heartbeat"
            assert val == heartbeat_at
            assert kwargs.get("ex") == settings.CELERY_HEARTBEAT_TTL_SECONDS

    def test_heartbeat_failure_returns_sanitized_error_code(self, caplog):
        """Verify worker_heartbeat_task sanitizes exceptions without leaking credentials or raw strings."""
        mock_redis = MagicMock()
        mock_redis.set.side_effect = ConnectionError("Connection to rediss://default:secret123@upstash.io failed")

        with patch("app.tasks.celery_app.get_redis_client", return_value=mock_redis):
            with caplog.at_level(logging.WARNING):
                result = worker_heartbeat_task(is_initial=False)

                assert result["status"] == "error"
                assert result["error_code"] == "REDIS_HEARTBEAT_ERROR"
                assert "detail" not in result
                assert "secret123" not in str(result)
                assert "Connection to rediss" not in str(result)

                # Ensure log message is sanitized
                for record in caplog.records:
                    assert "secret123" not in record.message
                    assert "Connection to rediss" not in record.message
                    assert "ConnectionError" in record.message

    def test_celery_task_routing_configuration(self):
        """Verify Celery task queues route deterministically to worker queues."""
        assert celery_app.conf.task_default_queue == "default"

        # Check beat schedule queues
        beat = celery_app.conf.beat_schedule
        assert beat["worker-heartbeat"]["options"]["queue"] == "default"
        assert beat["expire-dispatch-offers"]["options"]["queue"] == "default"


class TestHealthReadinessWorkerSemantics:
    """Verify /api/v1/health/ready handles active, missing, stale, and invalid heartbeats fail-closed."""

    @pytest.fixture
    def test_client(self):
        return TestClient(app)

    def test_readiness_active_heartbeat_returns_200_and_celery_healthy(self, test_client):
        """Fresh heartbeat within threshold marks worker active and celery healthy."""
        fresh_time = datetime.now(timezone.utc).isoformat()
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = fresh_time.encode("utf-8")

        with patch("app.tasks.celery_app.get_redis_client", return_value=mock_redis):
            with patch.object(settings, "ENVIRONMENT", "staging"):
                response = test_client.get("/api/v1/health/ready")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ready"
                assert data["services"]["celery"] == "healthy"
                assert data["checks"]["worker"] == "active"
                assert "worker_heartbeat_age_seconds" in data["checks"]
                assert data["checks"]["worker_heartbeat_age_seconds"] >= 0.0

    def test_readiness_missing_heartbeat_returns_503_in_staging(self, test_client):
        """Missing heartbeat in staging fails closed with HTTP 503 degraded."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = None  # key does not exist

        with patch("app.tasks.celery_app.get_redis_client", return_value=mock_redis):
            with patch.object(settings, "ENVIRONMENT", "staging"):
                response = test_client.get("/api/v1/health/ready")
                assert response.status_code == 503
                data = response.json()
                assert data["status"] == "degraded"
                assert data["services"]["celery"] == "unavailable"
                assert data["checks"]["worker"] == "missing"

    def test_readiness_stale_heartbeat_returns_503_in_staging(self, test_client):
        """Stale heartbeat exceeding threshold fails closed with HTTP 503 degraded."""
        stale_time = (datetime.now(timezone.utc) - timedelta(seconds=settings.CELERY_HEARTBEAT_THRESHOLD_SECONDS + 20)).isoformat()
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = stale_time.encode("utf-8")

        with patch("app.tasks.celery_app.get_redis_client", return_value=mock_redis):
            with patch.object(settings, "ENVIRONMENT", "staging"):
                response = test_client.get("/api/v1/health/ready")
                assert response.status_code == 503
                data = response.json()
                assert data["status"] == "degraded"
                assert data["services"]["celery"] == "degraded"
                assert data["checks"]["worker"] == "stale"
                assert data["checks"]["worker_heartbeat_age_seconds"] > settings.CELERY_HEARTBEAT_THRESHOLD_SECONDS

    def test_readiness_invalid_heartbeat_returns_503_in_staging(self, test_client):
        """Corrupted/invalid heartbeat format fails closed with HTTP 503 degraded."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = b"NOT_A_VALID_ISO_DATETIME"

        with patch("app.tasks.celery_app.get_redis_client", return_value=mock_redis):
            with patch.object(settings, "ENVIRONMENT", "staging"):
                response = test_client.get("/api/v1/health/ready")
                assert response.status_code == 503
                data = response.json()
                assert data["status"] == "degraded"
                assert data["services"]["celery"] == "unavailable"
                assert data["checks"]["worker"] == "invalid_heartbeat"
