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
