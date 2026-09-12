import pytest
from datetime import timedelta
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User

def test_register_citizen_success(client):
    payload = {
        "full_name": "Public Citizen",
        "email": "public_citizen@example.com",
        "phone": "+919999900001",
        "password": "strongpassword123"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Public Citizen"
    assert data["role"] == "CITIZEN"

def test_role_escalation_prevention(client, db):
    # Attacker attempts to register as SUPER_ADMIN or RESCUER
    payload = {
        "full_name": "Malicious User",
        "email": "attacker@example.com",
        "phone": "+919999900002",
        "password": "password123",
        "role": "SUPER_ADMIN"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "CITIZEN"

    # Confirm directly in the database
    user_db = db.query(User).filter(User.email == "attacker@example.com").first()
    assert user_db is not None
    assert user_db.role.value == "CITIZEN"

def test_login_success_and_failure(client, citizen_user):
    # Valid login
    res = client.post("/api/v1/auth/login", data={"username": citizen_user.email, "password": "password123"})
    assert res.status_code == 200
    tokens = res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"

    # Invalid password
    res_bad = client.post("/api/v1/auth/login", data={"username": citizen_user.email, "password": "wrongpassword"})
    assert res_bad.status_code == 401

def test_refresh_token_valid(client, citizen_user):
    login_res = client.post("/api/v1/auth/login", data={"username": citizen_user.email, "password": "password123"})
    assert login_res.status_code == 200
    refresh_tok = login_res.cookies.get("refresh_token") or login_res.json()["refresh_token"]
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_tok},
        cookies={"refresh_token": refresh_tok}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

def test_refresh_token_rejects_access_token(client, citizen_user):
    # An access token must not be accepted as a refresh token
    access_tok = create_access_token(citizen_user.id)
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": access_tok})
    assert response.status_code == 401
    assert "Invalid token type" in str(response.json())

def test_refresh_token_expired(client, citizen_user):
    # Expired token
    expired_tok = create_refresh_token(citizen_user.id, expires_delta=timedelta(seconds=-10))
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": expired_tok})
    assert response.status_code == 401

def test_refresh_token_malformed(client):
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "not.a.real.token"})
    assert response.status_code == 401
