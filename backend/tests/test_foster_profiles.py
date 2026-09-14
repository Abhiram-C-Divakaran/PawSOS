import uuid
import pytest
from app.models.user import User
from app.models.organization import Organization
from app.models.foster_home import FosterHome
from app.core.constants import UserRole, OrganizationType
from app.core.security import create_access_token, get_password_hash

def test_foster_caregiver_create_and_read_own_profile(client, foster_user, foster_token):
    # Create profile
    payload = {
        "locality": "Bandra West",
        "latitude": 19.0544,
        "longitude": 72.8402,
        "capacity": 2,
        "accepted_species": "Dog, Cat",
        "maximum_animal_size": "Medium",
        "medical_care_supported": True,
        "availability_status": "AVAILABLE",
    }
    res = client.post(
        "/api/v1/foster/profile",
        json=payload,
        headers={"Authorization": f"Bearer {foster_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["caregiver_id"] == str(foster_user.id)
    assert data["locality"] == "Bandra West"
    assert data["capacity"] == 2
    assert data["current_occupancy"] == 0
    # Crucial security check: self-verification must be denied / False
    assert data["verified"] is False
    assert data["verified_at"] is None

    # Read profile
    get_res = client.get(
        "/api/v1/foster/profile",
        headers={"Authorization": f"Bearer {foster_token}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == data["id"]
    assert get_res.json()["latitude"] == 19.0544


def test_foster_caregiver_cannot_self_verify(client, foster_token):
    # First create profile
    client.post(
        "/api/v1/foster/profile",
        json={"locality": "Bandra", "latitude": 19.05, "longitude": 72.83, "capacity": 2},
        headers={"Authorization": f"Bearer {foster_token}"},
    )
    # Attempt to pass verified: True in update
    res = client.patch(
        "/api/v1/foster/profile",
        json={"capacity": 3, "verified": True},
        headers={"Authorization": f"Bearer {foster_token}"},
    )
    assert res.status_code == 200
    # Verified should remain False
    assert res.json()["verified"] is False
    assert res.json()["capacity"] == 3


def test_unauthenticated_or_other_user_profile_isolation(client, db, citizen_token):
    # Unauthenticated
    res = client.get("/api/v1/foster/profile")
    assert res.status_code == 401

    # Citizen who has no foster profile
    res2 = client.get(
        "/api/v1/foster/profile",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert res2.status_code == 404


def test_ngo_manage_and_verify_foster_home(client, db, test_org, ngo_admin_token, foster_user):
    # Create foster home associated with test_org
    home = FosterHome(
        caregiver_id=foster_user.id,
        organization_id=test_org.id,
        locality="Khar West",
        latitude=19.0680,
        longitude=72.8350,
        capacity=3,
        current_occupancy=0,
        verified=False,
    )
    db.add(home)
    db.commit()
    db.refresh(home)

    # NGO lists homes
    list_res = client.get(
        "/api/v1/ngo/foster/homes",
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert list_res.status_code == 200
    assert any(h["id"] == str(home.id) for h in list_res.json())

    # NGO views specific home
    detail_res = client.get(
        f"/api/v1/ngo/foster/homes/{home.id}",
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert detail_res.status_code == 200
    assert detail_res.json()["locality"] == "Khar West"

    # NGO verifies home
    verify_res = client.post(
        f"/api/v1/ngo/foster/homes/{home.id}/verify",
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["verified"] is True
    assert verify_res.json()["verified_at"] is not None

    # NGO unverifies home
    unverify_res = client.post(
        f"/api/v1/ngo/foster/homes/{home.id}/unverify",
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert unverify_res.status_code == 200
    assert unverify_res.json()["verified"] is False


def test_cross_tenant_ngo_denial_and_null_org_fail_closed(client, db, test_org, foster_user):
    # Organization B
    org_b = Organization(
        name="Org B Shelter",
        organization_type=OrganizationType.NGO,
        email="org_b@example.com",
        phone="+912226003333",
        verification_status=True,
    )
    db.add(org_b)
    db.commit()
    db.refresh(org_b)

    # Home belongs to Org B
    home_b = FosterHome(
        caregiver_id=foster_user.id,
        organization_id=org_b.id,
        locality="Andheri East",
        latitude=19.1136,
        longitude=72.8697,
        capacity=2,
        current_occupancy=0,
    )
    db.add(home_b)

    # NGO Admin from Org A
    admin_a = User(
        full_name="Admin A",
        email="admin_a@example.com",
        phone="+919900000001",
        password_hash=get_password_hash("pass"),
        role=UserRole.NGO_ADMIN,
        organization_id=test_org.id,
        is_active=True,
    )
    # NGO Admin with null org
    admin_null_org = User(
        full_name="Admin Null",
        email="admin_null@example.com",
        phone="+919900000002",
        password_hash=get_password_hash("pass"),
        role=UserRole.NGO_ADMIN,
        organization_id=None,
        is_active=True,
    )
    db.add_all([admin_a, admin_null_org])
    db.commit()

    token_a = create_access_token(admin_a.id)
    token_null = create_access_token(admin_null_org.id)

    # Admin A attempts to access Home B -> Forbidden (cross-tenant)
    res1 = client.get(
        f"/api/v1/ngo/foster/homes/{home_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res1.status_code == 403

    # Admin A attempts to verify Home B -> Forbidden
    res2 = client.post(
        f"/api/v1/ngo/foster/homes/{home_b.id}/verify",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res2.status_code == 403

    # Admin with null org attempts to list homes -> Fails closed
    res3 = client.get(
        "/api/v1/ngo/foster/homes",
        headers={"Authorization": f"Bearer {token_null}"},
    )
    assert res3.status_code == 403
