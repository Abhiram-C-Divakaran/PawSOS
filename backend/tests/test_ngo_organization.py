import pytest
import uuid
from datetime import datetime

from app.models.user import User
from app.models.organization import Organization
from app.models.veterinary_facility import VeterinaryFacility
from app.models.audit_log import AuditLog
from app.core.constants import UserRole, OrganizationType
from app.core.security import get_password_hash, create_access_token

@pytest.fixture
def org_test_setup(db):
    org_a = Organization(
        name="Ernakulam Rescue Society",
        organization_type=OrganizationType.NGO,
        email="contact@ernakulamrescue.org",
        phone="+919847111111",
        operating_region="Kochi Metropolitan",
        description="Emergency animal response unit in Central Kerala",
    )
    db.add(org_a)

    org_b = Organization(
        name="Malabar Animal Haven",
        organization_type=OrganizationType.NGO,
        email="contact@malabarhaven.org",
        phone="+919847222222",
        operating_region="Calicut City",
        description="Rescue and shelter for street animals in Calicut",
    )
    db.add(org_b)
    db.commit()
    db.refresh(org_a)
    db.refresh(org_b)

    admin_a = User(
        full_name="Anjali Menon",
        email=f"anjali_{uuid.uuid4().hex[:6]}@ernakulamrescue.org",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.NGO_ADMIN,
        organization_id=org_a.id,
        is_active=True,
    )
    db.add(admin_a)

    admin_b = User(
        full_name="Rohan Varma",
        email=f"rohan_{uuid.uuid4().hex[:6]}@malabarhaven.org",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.NGO_ADMIN,
        organization_id=org_b.id,
        is_active=True,
    )
    db.add(admin_b)

    # Responders in Org A
    rescuer_a1 = User(
        full_name="Kochi Rescuer 1",
        email=f"rescuer1_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9197{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.RESCUER,
        organization_id=org_a.id,
        is_active=True,
    )
    db.add(rescuer_a1)

    # Vet facility in Org A
    fac_a = VeterinaryFacility(
        name="Kochi Emergency Vet Hospital",
        phone="+914842345678",
        email="fac@ernakulamrescue.org",
        latitude=9.9816,
        longitude=76.2999,
        organization_id=org_a.id,
        is_verified=True,
    )
    db.add(fac_a)

    db.commit()
    db.refresh(admin_a)
    db.refresh(admin_b)

    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "token_a": create_access_token(admin_a.id),
        "token_b": create_access_token(admin_b.id),
    }

def test_get_organization_profile_success(client, org_test_setup):
    token = org_test_setup["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/ngo/organization", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["name"] == "Ernakulam Rescue Society"
    assert data["operating_region"] == "Kochi Metropolitan"
    assert data["description"] == "Emergency animal response unit in Central Kerala"
    assert data["responders_count"] == 1
    assert data["veterinary_partners_count"] == 1
    assert "created_at" in data

def test_patch_organization_profile_and_audit(client, db, org_test_setup):
    token = org_test_setup["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    update_payload = {
        "operating_region": "Greater Kochi & Aluva Region",
        "description": "Expanded animal ambulance and paramedic network",
        "phone": "+919847333333",
    }
    res = client.patch("/api/v1/ngo/organization", json=update_payload, headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["operating_region"] == "Greater Kochi & Aluva Region"
    assert data["description"] == "Expanded animal ambulance and paramedic network"
    assert data["phone"] == "+919847333333"

    # Verify audit log in DB
    audit = db.query(AuditLog).filter(
        AuditLog.action == "UPDATE_ORGANIZATION_PROFILE",
        AuditLog.entity_id == org_test_setup["org_a"].id
    ).first()
    assert audit is not None
    assert audit.actor_id == org_test_setup["admin_a"].id
    assert audit.new_value["operating_region"] == "Greater Kochi & Aluva Region"

def test_organization_tenant_isolation(client, org_test_setup):
    token_b = org_test_setup["token_b"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    res = client.get("/api/v1/ngo/organization", headers=headers_b)
    assert res.status_code == 200
    data = res.json()

    assert data["name"] == "Malabar Animal Haven"
    assert data["operating_region"] == "Calicut City"
    # Org B has 0 responders and 0 vet facilities
    assert data["responders_count"] == 0
    assert data["veterinary_partners_count"] == 0

def test_organization_unauthorized_roles(client, citizen_token, rescuer_token):
    res_citizen = client.get("/api/v1/ngo/organization", headers={"Authorization": f"Bearer {citizen_token}"})
    assert res_citizen.status_code == 403

    res_rescuer = client.get("/api/v1/ngo/organization", headers={"Authorization": f"Bearer {rescuer_token}"})
    assert res_rescuer.status_code == 403

def test_cross_tenant_responder_assignment_blocked(client, db, org_test_setup):
    from app.models.rescue_case import RescueCase
    from app.core.constants import RescueStatus

    # Create a rescuer in Org B
    rescuer_b = User(
        full_name="Calicut Rescuer B",
        email=f"rescuer_b_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9197{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.RESCUER,
        organization_id=org_test_setup["org_b"].id,
        is_active=True,
    )
    db.add(rescuer_b)

    # Create a case in Org A
    case_a = RescueCase(
        case_number=f"CASE-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=org_test_setup["admin_a"].id,
        species="Dog",
        latitude=9.9816,
        longitude=76.2999,
        status=RescueStatus.SEARCHING_RESPONDER,
        organization_id=org_test_setup["org_a"].id,
    )
    db.add(case_a)
    db.commit()

    # Admin A attempts to manually assign Rescuer B to Case A
    token_a = org_test_setup["token_a"]
    resp = client.post(
        f"/api/v1/ngo/cases/{case_a.id}/action",
        json={"action": "assign_responder", "rescuer_id": str(rescuer_b.id)},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 403
    assert "Cannot assign responder from another organization" in resp.json()["detail"]

    # Verify audit log was written
    audit = db.query(AuditLog).filter(
        AuditLog.action == "CROSS_TENANT_RESPONDER_ASSIGNMENT_DENIED",
        AuditLog.entity_id == case_a.id,
    ).first()
    assert audit is not None
    assert audit.actor_id == org_test_setup["admin_a"].id

def test_cross_tenant_facility_assignment_blocked(client, db, org_test_setup):
    from app.models.rescue_case import RescueCase
    from app.core.constants import RescueStatus

    # Private facility in Org B
    fac_b = VeterinaryFacility(
        name="Calicut Private Clinic",
        phone="+914952345678",
        latitude=11.2588,
        longitude=75.7804,
        organization_id=org_test_setup["org_b"].id,
        is_verified=True,
    )
    db.add(fac_b)

    # Case in Org A
    case_a = RescueCase(
        case_number=f"CASE-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=org_test_setup["admin_a"].id,
        species="Cat",
        latitude=9.9816,
        longitude=76.2999,
        status=RescueStatus.RESCUED,
        organization_id=org_test_setup["org_a"].id,
    )
    db.add(case_a)
    db.commit()

    # Admin A attempts to change facility to Facility B
    token_a = org_test_setup["token_a"]
    resp = client.post(
        f"/api/v1/ngo/cases/{case_a.id}/action",
        json={"action": "change_facility", "veterinary_facility_id": str(fac_b.id)},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 403
    assert "Cannot assign private veterinary facility of another organization" in resp.json()["detail"]

    # Verify audit log
    audit = db.query(AuditLog).filter(
        AuditLog.action == "CROSS_TENANT_FACILITY_ASSIGNMENT_DENIED",
        AuditLog.entity_id == case_a.id,
    ).first()
    assert audit is not None
    assert audit.actor_id == org_test_setup["admin_a"].id
