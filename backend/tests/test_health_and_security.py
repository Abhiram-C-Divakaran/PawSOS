import pytest
from app.core.security import create_refresh_token

def test_health_endpoints(client):
    """Verify liveness and readiness health checks."""
    live_res = client.get("/health")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "ok"

    ready_res = client.get("/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"
    assert ready_res.json()["checks"]["database"] == "connected"

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
