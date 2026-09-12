import pytest
from app.core.security import create_refresh_token

def test_health_endpoints(client):
    """Verify root alias liveness and readiness health checks."""
    live_res = client.get("/health")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "ok"

    ready_res = client.get("/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] in ["ready", "degraded"]
    assert ready_res.json()["checks"]["database"] == "connected"

    readiness_alias = client.get("/health/readiness")
    assert readiness_alias.status_code == 200
    assert readiness_alias.json()["status"] == ready_res.json()["status"]

def test_canonical_api_v1_health_endpoints(client):
    """Verify canonical /api/v1 public health routing contracts."""
    live_res = client.get("/api/v1/health")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "ok"

    ready_res = client.get("/api/v1/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] in ["ready", "degraded"]
    assert ready_res.json()["services"]["database"] == "healthy"
    assert "postgis" in ready_res.json()["services"]
    assert "storage" in ready_res.json()["services"]
    assert "firebase" in ready_res.json()["services"]

    readiness_res = client.get("/api/v1/health/readiness")
    assert readiness_res.status_code == 200
    assert readiness_res.json()["services"]["database"] == "healthy"

def test_readiness_database_failure(client, monkeypatch):
    """Verify readiness returns 503 and offline status when database fails."""
    from unittest.mock import MagicMock
    from app.database import get_db

    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("Database connection lost")

    from app.main import app
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        res = client.get("/api/v1/health/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "offline"
        assert data["checks"]["database"] == "disconnected"
    finally:
        app.dependency_overrides.pop(get_db, None)

def test_security_headers_present(client):
    """Verify production security headers are applied to HTTP responses."""
    res = client.get("/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "strict-origin" in res.headers.get("Referrer-Policy", "")
    assert "default-src" in res.headers.get("Content-Security-Policy", "")

def test_refresh_token_rotation_and_cookies(client, citizen_user):
    """Verify refresh token rotation and HttpOnly cookie generation on refresh."""
    # Login with credentials
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": citizen_user.phone, "password": "password123"}
    )
    assert login_res.status_code == 200
    data = login_res.json()
    first_refresh = data["refresh_token"]
    assert "set-cookie" in login_res.headers

    # Refresh token rotation
    refresh_res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh}
    )
    assert refresh_res.status_code == 200
    second_refresh = refresh_res.json()["refresh_token"]
    assert second_refresh != first_refresh  # Rotated!

    # Logout
    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200


def test_readiness_worker_heartbeat_scenarios(client, monkeypatch):
    """Verify fail-closed worker heartbeat readiness under valid, stale, invalid, missing, and redis error states."""
    from unittest.mock import MagicMock
    from datetime import datetime, timezone, timedelta
    from app.config import settings
    import redis

    # Scenario 1: Fresh valid heartbeat
    now_iso = datetime.now(timezone.utc).isoformat()
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = now_iso.encode("utf-8")

    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(redis, "from_url", lambda *args, **kwargs: mock_redis)

    res = client.get("/api/v1/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["checks"]["redis"] == "connected"
    assert data["checks"]["worker"] == "active"
    assert data["services"]["celery"] == "healthy"

    # Scenario 2: Stale heartbeat (age > threshold)
    stale_iso = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    mock_redis.get.return_value = stale_iso.encode("utf-8")
    monkeypatch.setenv("REQUIRE_FULL_READINESS", "true")

    res = client.get("/api/v1/health/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["checks"]["worker"] == "stale"
    assert data["services"]["celery"] == "degraded"

    # Scenario 3: Invalid unparseable heartbeat content
    mock_redis.get.return_value = b"NOT_A_VALID_DATETIME_STRING"
    res = client.get("/api/v1/health/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["checks"]["worker"] == "invalid_heartbeat"
    assert data["services"]["celery"] == "unavailable"

    # Scenario 4: Missing heartbeat key (None)
    mock_redis.get.return_value = None
    res = client.get("/api/v1/health/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["checks"]["worker"] == "missing"
    assert data["services"]["celery"] == "unavailable"

    # Scenario 5: Redis connection failure
    mock_failing_redis = MagicMock()
    mock_failing_redis.ping.side_effect = Exception("Connection refused")
    monkeypatch.setattr(redis, "from_url", lambda *args, **kwargs: mock_failing_redis)

    res = client.get("/api/v1/health/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["checks"]["redis"] == "disconnected"
    assert data["checks"]["worker"] == "unavailable"
    assert data["services"]["redis"] == "unavailable"
    assert data["services"]["celery"] == "unavailable"

