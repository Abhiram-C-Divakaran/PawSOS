import pytest
import uuid

from app.models.user import User
from app.models.organization import Organization
from app.core.constants import UserRole, OrganizationType
from app.core.security import get_password_hash, create_access_token

@pytest.fixture
def settings_test_setup(db):
    org = Organization(
        name="Thrissur Animal Lifeline",
        organization_type=OrganizationType.NGO,
        email="contact@thrissuranimal.org",
        phone="+919847444444",
        operating_region="Thrissur District",
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    ngo_user = User(
        full_name="Deepa Nair",
        email=f"deepa_{uuid.uuid4().hex[:6]}@thrissuranimal.org",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.NGO_ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    db.add(ngo_user)
    db.commit()
    db.refresh(ngo_user)

    return {
        "user": ngo_user,
        "token": create_access_token(ngo_user.id),
    }

def test_get_dispatch_settings_success(client, settings_test_setup):
    token = settings_test_setup["token"]
    res = client.get("/api/v1/ngo/settings/dispatch", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert "default_radius_km" in data
    assert "radius_escalation_levels" in data
    assert isinstance(data["radius_escalation_levels"], list)
    assert len(data["radius_escalation_levels"]) > 0
    assert "offer_expiration_seconds" in data
    assert "stale_location_timeout_seconds" in data
    assert data["default_radius_km"] == 5.0
    assert 10.0 in data["radius_escalation_levels"]

def test_dispatch_settings_forbidden_for_citizen(client, citizen_token):
    res = client.get("/api/v1/ngo/settings/dispatch", headers={"Authorization": f"Bearer {citizen_token}"})
    assert res.status_code == 403

def test_get_and_patch_user_preferences(client, settings_test_setup, db):
    token = settings_test_setup["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Initial get
    res_get = client.get("/api/v1/auth/me/preferences", headers=headers)
    assert res_get.status_code == 200
    initial_prefs = res_get.json()
    assert initial_prefs["critical_rescue_alerts"] is True
    assert initial_prefs["dispatch_failures"] is True

    # Update preferences
    patch_payload = {
        "critical_rescue_alerts": True,
        "dispatch_failures": False,
        "veterinary_updates": True,
        "case_closures": False,
    }
    res_patch = client.patch("/api/v1/auth/me/preferences", json=patch_payload, headers=headers)
    assert res_patch.status_code == 200
    updated_prefs = res_patch.json()

    assert updated_prefs["critical_rescue_alerts"] is True
    assert updated_prefs["dispatch_failures"] is False
    assert updated_prefs["veterinary_updates"] is True
    assert updated_prefs["case_closures"] is False

    # Verify persistence by reading user from DB
    user_db = db.query(User).filter(User.id == settings_test_setup["user"].id).first()
    assert user_db.notification_preferences["dispatch_failures"] is False
    assert user_db.notification_preferences["case_closures"] is False
