import pytest
import uuid
from datetime import datetime
from app.models.user import User
from app.models.organization import Organization
from app.models.veterinary_facility import VeterinaryFacility
from app.models.rescue_case import RescueCase
from app.models.treatment import Treatment
from app.core.constants import UserRole, RescueStatus, RescuePriority, OrganizationType
from app.core.security import get_password_hash, create_access_token

@pytest.fixture
def scoping_env(db):
    pwd = get_password_hash("password123")

    # Organizations
    org_a = Organization(
        name="Org Alpha Rescue",
        organization_type=OrganizationType.NGO,
        phone="+919800000001",
        email="alpha@org.com",
        address="Kochi",
        verification_status=True,
    )
    org_b = Organization(
        name="Org Beta Shelter",
        organization_type=OrganizationType.NGO,
        phone="+919800000002",
        email="beta@org.com",
        address="Kozhikode",
        verification_status=True,
    )
    db.add_all([org_a, org_b])
    db.commit()

    # Users
    admin_a = User(
        full_name="Admin Alpha",
        email="admin.alpha@pawsos.org",
        phone="+919810000001",
        password_hash=pwd,
        role=UserRole.NGO_ADMIN,
        organization_id=org_a.id,
        is_active=True,
        is_verified=True,
    )
    admin_b = User(
        full_name="Admin Beta",
        email="admin.beta@pawsos.org",
        phone="+919810000002",
        password_hash=pwd,
        role=UserRole.NGO_ADMIN,
        organization_id=org_b.id,
        is_active=True,
        is_verified=True,
    )
    super_admin = User(
        full_name="Super Admin",
        email="superadmin@pawsos.org",
        phone="+919810000003",
        password_hash=pwd,
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_verified=True,
    )
    citizen = User(
        full_name="Citizen Scoping",
        email="citizen.scope@pawsos.org",
        phone="+919810000004",
        password_hash=pwd,
        role=UserRole.CITIZEN,
        is_active=True,
        is_verified=True,
    )

    # Veterinary Facilities
    fac_1 = VeterinaryFacility(
        name="Clinic One",
        phone="+919820000001",
        email="c1@vet.com",
        latitude=9.9312,
        longitude=76.2673,
        location="POINT(76.2673 9.9312)",
        address="Kochi",
        is_verified=True,
    )
    fac_2 = VeterinaryFacility(
        name="Clinic Two",
        phone="+919820000002",
        email="c2@vet.com",
        latitude=10.0000,
        longitude=76.3000,
        location="POINT(76.3000 10.0000)",
        address="Aluva",
        is_verified=True,
    )
    db.add_all([admin_a, admin_b, super_admin, citizen, fac_1, fac_2])
    db.commit()

    vet_1 = User(
        full_name="Vet Facility 1",
        email="vet1@pawsos.org",
        phone="+919830000001",
        password_hash=pwd,
        role=UserRole.VETERINARIAN,
        veterinary_facility_id=fac_1.id,
        is_active=True,
        is_verified=True,
    )
    vet_2 = User(
        full_name="Vet Facility 2",
        email="vet2@pawsos.org",
        phone="+919830000002",
        password_hash=pwd,
        role=UserRole.VETERINARIAN,
        veterinary_facility_id=fac_2.id,
        is_active=True,
        is_verified=True,
    )
    db.add_all([vet_1, vet_2])
    db.commit()

    # Cases
    case_a = RescueCase(
        case_number=f"PR-A-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=citizen.id,
        species="Dog",
        description="Alpha org case",
        latitude=9.9312,
        longitude=76.2673,
        status=RescueStatus.SEARCHING_RESPONDER,
        triage_priority=RescuePriority.URGENT,
        organization_id=org_a.id,
    )
    case_b = RescueCase(
        case_number=f"PR-B-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=citizen.id,
        species="Cat",
        description="Beta org case",
        latitude=10.0000,
        longitude=76.3000,
        status=RescueStatus.SEARCHING_RESPONDER,
        triage_priority=RescuePriority.MODERATE,
        organization_id=org_b.id,
    )
    case_vet_2 = RescueCase(
        case_number=f"PR-VET2-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=citizen.id,
        species="Puppy",
        description="Under treatment at clinic 2",
        latitude=10.0000,
        longitude=76.3000,
        status=RescueStatus.AT_VETERINARY_FACILITY,
        triage_priority=RescuePriority.URGENT,
        veterinary_facility_id=fac_2.id,
    )
    db.add_all([case_a, case_b, case_vet_2])
    db.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "super_admin": super_admin,
        "vet_1": vet_1,
        "vet_2": vet_2,
        "fac_1": fac_1,
        "fac_2": fac_2,
        "case_a": case_a,
        "case_b": case_b,
        "case_vet_2": case_vet_2,
    }

def test_ngo_admin_cross_tenant_dossier_forbidden(client, scoping_env):
    admin_a = scoping_env["admin_a"]
    case_b = scoping_env["case_b"]
    token_a = create_access_token(admin_a.id)

    # Admin A trying to access Case B's dossier must receive 403 Forbidden
    resp = client.get(
        f"/api/v1/ngo/cases/{case_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 403
    assert "belongs to another organization" in resp.json()["detail"].lower()

def test_ngo_admin_authorized_dossier_success(client, scoping_env):
    admin_a = scoping_env["admin_a"]
    case_a = scoping_env["case_a"]
    token_a = create_access_token(admin_a.id)

    resp = client.get(
        f"/api/v1/ngo/cases/{case_a.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(case_a.id)

def test_ngo_admin_cases_list_tenant_isolation(client, scoping_env):
    admin_a = scoping_env["admin_a"]
    case_a = scoping_env["case_a"]
    case_b = scoping_env["case_b"]
    token_a = create_access_token(admin_a.id)

    resp = client.get(
        "/api/v1/ngo/cases",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    case_ids = [c["id"] for c in resp.json()]
    assert str(case_a.id) in case_ids
    assert str(case_b.id) not in case_ids

def test_super_admin_global_scoping_bypass(client, scoping_env):
    super_admin = scoping_env["super_admin"]
    case_a = scoping_env["case_a"]
    case_b = scoping_env["case_b"]
    super_token = create_access_token(super_admin.id)

    # Super Admin can view Case B's dossier without 403
    resp_b = client.get(
        f"/api/v1/ngo/cases/{case_b.id}",
        headers={"Authorization": f"Bearer {super_token}"},
    )
    assert resp_b.status_code == 200

    # Super Admin sees both cases in list
    resp_list = client.get(
        "/api/v1/ngo/cases",
        headers={"Authorization": f"Bearer {super_token}"},
    )
    assert resp_list.status_code == 200
    all_case_ids = [c["id"] for c in resp_list.json()]
    assert str(case_a.id) in all_case_ids
    assert str(case_b.id) in all_case_ids

def test_veterinarian_facility_scoping_isolation(client, scoping_env):
    vet_1 = scoping_env["vet_1"]
    vet_2 = scoping_env["vet_2"]
    fac_1 = scoping_env["fac_1"]
    fac_2 = scoping_env["fac_2"]
    case_vet_2 = scoping_env["case_vet_2"]

    token_vet_1 = create_access_token(vet_1.id)
    token_vet_2 = create_access_token(vet_2.id)

    # Vet 1 querying treatments for case assigned to Facility 2 gets 403 Forbidden
    resp = client.get(
        f"/api/v1/rescues/{case_vet_2.id}/treatments",
        headers={"Authorization": f"Bearer {token_vet_1}"},
    )
    assert resp.status_code == 403
    assert "another veterinary facility" in str(resp.json())

    # Vet 1 attempting to add treatment for facility 2 case gets 403 Forbidden
    post_resp = client.post(
        f"/api/v1/rescues/{case_vet_2.id}/treatments",
        headers={"Authorization": f"Bearer {token_vet_1}"},
        json={
            "facility_id": str(fac_1.id),
            "diagnosis": "Leg Fracture",
            "treatment_notes": "Attempted cross-facility entry",
        },
    )
    assert post_resp.status_code == 403

    # Vet 2 (authorized clinic) can query treatments successfully
    resp_ok = client.get(
        f"/api/v1/rescues/{case_vet_2.id}/treatments",
        headers={"Authorization": f"Bearer {token_vet_2}"},
    )
    assert resp_ok.status_code == 200
