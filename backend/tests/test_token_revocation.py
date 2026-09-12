import pytest
import uuid
from datetime import datetime, timedelta
from app.models.user import User
from app.models.refresh_session import RefreshSession
from app.core.constants import UserRole
from app.core.security import get_password_hash, create_refresh_token, decode_token, hash_jti

@pytest.fixture
def auth_user(db):
    pwd = get_password_hash("securepass123")
    user = User(
        full_name="Auth Tester",
        email=f"authtest_{uuid.uuid4().hex[:6]}@pawsos.org",
        phone=f"+9199{uuid.uuid4().hex[:8]}",
        password_hash=pwd,
        role=UserRole.CITIZEN,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def test_login_creates_refresh_session(client, db, auth_user):
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": auth_user.email, "password": "securepass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in resp.cookies or data.get("refresh_token") is not None

    # Verify session recorded in database
    sessions = db.query(RefreshSession).filter(RefreshSession.user_id == auth_user.id).all()
    assert len(sessions) == 1
    assert sessions[0].revoked_at is None
    assert sessions[0].expires_at > datetime.utcnow()

def test_token_rotation_and_revocation(client, db, auth_user):
    # 1. Initial Login
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": auth_user.email, "password": "securepass123"},
    )
    assert login_resp.status_code == 200
    first_refresh = login_resp.cookies.get("refresh_token") or login_resp.json().get("refresh_token")
    assert first_refresh is not None

    first_payload = decode_token(first_refresh)
    first_hash = hash_jti(first_payload["jti"])
    first_session = db.query(RefreshSession).filter(RefreshSession.token_hash == first_hash).first()
    assert first_session is not None
    assert first_session.revoked_at is None

    # 2. Refresh Token
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh},
        cookies={"refresh_token": first_refresh},
    )
    assert refresh_resp.status_code == 200
    second_refresh = refresh_resp.cookies.get("refresh_token") or refresh_resp.json().get("refresh_token")
    assert second_refresh is not None
    assert second_refresh != first_refresh

    # 3. Verify First Session Revoked & Replaced
    db.refresh(first_session)
    assert first_session.revoked_at is not None
    assert first_session.replaced_by is not None

    # 4. Verify Second Session Active
    second_payload = decode_token(second_refresh)
    second_hash = hash_jti(second_payload["jti"])
    second_session = db.query(RefreshSession).filter(RefreshSession.token_hash == second_hash).first()
    assert second_session is not None
    assert str(second_session.id) == first_session.replaced_by
    assert second_session.revoked_at is None

def test_replay_attack_detection(client, db, auth_user):
    # 1. Login
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": auth_user.email, "password": "securepass123"},
    )
    first_refresh = login_resp.cookies.get("refresh_token") or login_resp.json().get("refresh_token")

    # 2. Legitimate Refresh (rotates first token)
    rot_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh},
        cookies={"refresh_token": first_refresh},
    )
    assert rot_resp.status_code == 200
    second_refresh = rot_resp.cookies.get("refresh_token") or rot_resp.json().get("refresh_token")
    second_payload = decode_token(second_refresh)
    second_session = db.query(RefreshSession).filter(
        RefreshSession.token_hash == hash_jti(second_payload["jti"])
    ).first()
    assert second_session.revoked_at is None

    # 3. Malicious Replay of First (now revoked) Token
    replay_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh},
        cookies={"refresh_token": first_refresh},
    )
    assert replay_resp.status_code == 401
    detail = replay_resp.json().get("detail", {})
    msg = detail.get("error", {}).get("message", "") if isinstance(detail, dict) else str(detail)
    assert "revoked" in msg.lower()

    # 4. Verify Cascading Revocation of Downstream Token Chain
    db.refresh(second_session)
    assert second_session.revoked_at is not None

def test_single_device_logout(client, db, auth_user):
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": auth_user.email, "password": "securepass123"},
    )
    refresh_token = login_resp.cookies.get("refresh_token") or login_resp.json().get("refresh_token")

    logout_resp = client.post(
        "/api/v1/auth/logout",
        cookies={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200

    # Verify session revoked
    payload = decode_token(refresh_token)
    session = db.query(RefreshSession).filter(
        RefreshSession.token_hash == hash_jti(payload["jti"])
    ).first()
    assert session.revoked_at is not None

    # Refresh attempt fails
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401

def test_logout_all_devices(client, db, auth_user):
    # Device 1 Login
    resp1 = client.post(
        "/api/v1/auth/login",
        data={"username": auth_user.email, "password": "securepass123"},
        headers={"User-Agent": "Device-1-Browser"},
    )
    access_token = resp1.json()["access_token"]

    # Device 2 Login
    client.post(
        "/api/v1/auth/login",
        data={"username": auth_user.email, "password": "securepass123"},
        headers={"User-Agent": "Device-2-Mobile"},
    )

    # Active sessions should be 2
    active_sessions = db.query(RefreshSession).filter(
        RefreshSession.user_id == auth_user.id,
        RefreshSession.revoked_at.is_(None),
    ).all()
    assert len(active_sessions) == 2

    # Call /auth/logout-all
    logout_all_resp = client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_all_resp.status_code == 200

    # All sessions should now be revoked
    remaining_active = db.query(RefreshSession).filter(
        RefreshSession.user_id == auth_user.id,
        RefreshSession.revoked_at.is_(None),
    ).count()
    assert remaining_active == 0
