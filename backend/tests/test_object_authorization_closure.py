"""Regression suite for Object-Level Authorization Closure & Security Boundary Hardening.

Covers:
1. Rescue status update authorization:
   - Citizen: reporter only (cross-citizen gets 403)
   - Rescuer: accepted assignment only (unrelated rescuer gets 403)
   - Veterinarian: exact facility match (foreign vet gets 403, null case facility gets 403)
   - NGO Admin: exact org match, non-null (cross-tenant gets 403, null-org gets 403, unassigned gets 403)
   - Super Admin: global access (200)
2. Treatment read and write authorization:
   - POST /rescues/{case_id}/treatments: non-null matching facility required, no auto-claiming
   - GET /rescues/{case_id}/treatments: scoped to authorized actors
3. Animal record BOLA closure:
   - Citizen role removed from GET and PATCH /animals/{animal_id} (403)
   - Unrelated actors denied (403)
   - Actors linked through cases allowed (200)
4. NGO Admin null-org fail-closed across all private endpoints (403)
5. NGO analytics strictly limited to own-tenant claimed cases (unassigned excluded)
6. Explicit claim only: unassigned case action fails closed (403), no auto-claiming
7. Responder assignment blocks unaffiliated (403), foreign (403), and inactive (400) responders
"""

import uuid
from datetime import datetime
import pytest
from starlette.testclient import TestClient

from app.models.user import User
from app.models.animal import Animal
from app.models.rescue_case import RescueCase
from app.models.treatment import Treatment
from app.models.organization import Organization
from app.models.veterinary_facility import VeterinaryFacility
from app.models.rescue_assignment import RescueAssignment
from app.models.rescuer_profile import RescuerProfile
from app.core.constants import UserRole, RescueStatus, AssignmentStatus, OrganizationType
from app.core.security import create_access_token


@pytest.fixture
def auth_env(db):
    """Setup multi-tenant users, organizations, facilities, and cases."""
    # 1. Organizations
    org_alpha = Organization(
        name="Org Alpha",
        organization_type=OrganizationType.NGO,
        email=f"alpha_{uuid.uuid4().hex[:6]}@test.org",
        phone="+919876543210",
        address="Kochi, Kerala",
    )
    org_beta = Organization(
        name="Org Beta",
        organization_type=OrganizationType.NGO,
        email=f"beta_{uuid.uuid4().hex[:6]}@test.org",
        phone="+919876543211",
        address="Calicut, Kerala",
    )
    db.add_all([org_alpha, org_beta])
    db.commit()
    db.refresh(org_alpha)
    db.refresh(org_beta)

    # 2. Veterinary Facilities
    fac_1 = VeterinaryFacility(
        name="Cochin PetCare Emergency Hospital",
        organization_id=org_alpha.id,
        latitude=9.9850,
        longitude=76.2980,
        address="Marine Drive, Kochi",
        phone="+919876543220",
        email=f"fac1_{uuid.uuid4().hex[:6]}@test.org",
        is_verified=True,
    )
    fac_2 = VeterinaryFacility(
        name="Malabar Animal Hospital",
        organization_id=org_beta.id,
        latitude=11.2588,
        longitude=75.7804,
        address="Beach Road, Calicut",
        phone="+919876543221",
        email=f"fac2_{uuid.uuid4().hex[:6]}@test.org",
        is_verified=True,
    )
    db.add_all([fac_1, fac_2])
    db.commit()
    db.refresh(fac_1)
    db.refresh(fac_2)

    # 3. Users
    def make_user(role, email_prefix, org_id=None, fac_id=None, is_active=True):
        u = User(
            email=f"{email_prefix}_{uuid.uuid4().hex[:6]}@test.org",
            password_hash="test_password_hash",
            role=role,
            full_name=f"{email_prefix.title()} User",
            phone=f"+91{uuid.uuid4().int % 10000000000:010d}",
            organization_id=org_id,
            veterinary_facility_id=fac_id,
            is_active=is_active,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u

    citizen_reporter = make_user(UserRole.CITIZEN, "cit_reporter")
    citizen_other = make_user(UserRole.CITIZEN, "cit_other")

    rescuer_assigned = make_user(UserRole.RESCUER, "resc_assigned", org_id=org_alpha.id)
    rescuer_unrelated = make_user(UserRole.RESCUER, "resc_unrelated", org_id=org_alpha.id)
    rescuer_foreign = make_user(UserRole.RESCUER, "resc_foreign", org_id=org_beta.id)
    rescuer_unaffiliated = make_user(UserRole.RESCUER, "resc_unaffil", org_id=None)
    rescuer_inactive = make_user(UserRole.RESCUER, "resc_inactive", org_id=org_alpha.id, is_active=False)

    # Create profiles for rescuers
    for r in [rescuer_assigned, rescuer_unrelated, rescuer_foreign, rescuer_unaffiliated, rescuer_inactive]:
        prof = RescuerProfile(user_id=r.id, organization_id=r.organization_id)
        db.add(prof)
    db.commit()

    vet_alpha = make_user(UserRole.VETERINARIAN, "vet_alpha", fac_id=fac_1.id)
    vet_beta = make_user(UserRole.VETERINARIAN, "vet_beta", fac_id=fac_2.id)
    vet_null = make_user(UserRole.VETERINARIAN, "vet_null", fac_id=None)

    admin_alpha = make_user(UserRole.NGO_ADMIN, "admin_alpha", org_id=org_alpha.id)
    admin_beta = make_user(UserRole.NGO_ADMIN, "admin_beta", org_id=org_beta.id)
    admin_null_org = make_user(UserRole.NGO_ADMIN, "admin_null", org_id=None)

    super_admin = make_user(UserRole.SUPER_ADMIN, "super_admin")

    # 4. Animals & Cases
    animal_alpha = Animal(species="Dog", description="Bruno")
    animal_unassigned = Animal(species="Cat", description="Whiskers")
    db.add_all([animal_alpha, animal_unassigned])
    db.commit()
    db.refresh(animal_alpha)
    db.refresh(animal_unassigned)

    # Claimed case (Org Alpha, Fac 1, Rescuer Assigned accepted)
    case_alpha = RescueCase(
        case_number=f"CASE-ALPHA-{uuid.uuid4().hex[:4]}",
        reporter_id=citizen_reporter.id,
        animal_id=animal_alpha.id,
        species="Dog",
        description="Alpha claimed case",
        latitude=9.9850,
        longitude=76.2980,
        address_text="Marine Drive, Kochi",
        status=RescueStatus.RESPONDER_ASSIGNED,
        organization_id=org_alpha.id,
        veterinary_facility_id=fac_1.id,
    )
    # Unassigned case
    case_unassigned = RescueCase(
        case_number=f"CASE-UNASS-{uuid.uuid4().hex[:4]}",
        reporter_id=citizen_reporter.id,
        animal_id=animal_unassigned.id,
        species="Cat",
        description="Unassigned case",
        latitude=9.9860,
        longitude=76.2990,
        address_text="High Court Jetty, Kochi",
        status=RescueStatus.SEARCHING_RESPONDER,
        organization_id=None,
        veterinary_facility_id=None,
    )
    db.add_all([case_alpha, case_unassigned])
    db.commit()
    db.refresh(case_alpha)
    db.refresh(case_unassigned)

    # Assignment for rescuer_assigned on case_alpha
    assignment = RescueAssignment(
        rescue_case_id=case_alpha.id,
        rescuer_id=rescuer_assigned.id,
        assignment_status=AssignmentStatus.ACCEPTED,
        accepted_at=datetime.utcnow(),
    )
    db.add(assignment)
    db.commit()

    def token_for(user):
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return {
        "org_alpha": org_alpha,
        "org_beta": org_beta,
        "fac_1": fac_1,
        "fac_2": fac_2,
        "animal_alpha": animal_alpha,
        "animal_unassigned": animal_unassigned,
        "case_alpha": case_alpha,
        "case_unassigned": case_unassigned,
        "citizen_reporter": citizen_reporter,
        "citizen_other": citizen_other,
        "rescuer_assigned": rescuer_assigned,
        "rescuer_unrelated": rescuer_unrelated,
        "rescuer_foreign": rescuer_foreign,
        "rescuer_unaffiliated": rescuer_unaffiliated,
        "rescuer_inactive": rescuer_inactive,
        "vet_alpha": vet_alpha,
        "vet_beta": vet_beta,
        "vet_null": vet_null,
        "admin_alpha": admin_alpha,
        "admin_beta": admin_beta,
        "admin_null_org": admin_null_org,
        "super_admin": super_admin,
        "token": token_for,
    }


def test_rescue_status_update_authorization(client: TestClient, db, auth_env):
    """Verify strict object-level authorization on PATCH /api/v1/rescues/{case_id}/status."""
    env = auth_env
    case = env["case_alpha"]
    case_url = f"/api/v1/rescues/{case.id}/status"

    # 1. Citizen: reporter allowed to cancel reported case, other citizen denied (403)
    resp = client.patch(case_url, json={"status": "CANCELLED"}, headers=env["token"](env["citizen_other"]))
    assert resp.status_code == 403

    # Reporter can cancel their own case in REPORTED status
    case_rep = RescueCase(
        case_number=f"CASE-REP-{uuid.uuid4().hex[:4]}",
        reporter_id=env["citizen_reporter"].id,
        animal_id=env["animal_alpha"].id,
        species="Dog",
        description="Fresh reported case",
        latitude=9.9850,
        longitude=76.2980,
        status=RescueStatus.REPORTED,
    )
    db.add(case_rep)
    db.commit()
    db.refresh(case_rep)
    rep_cancel = client.patch(f"/api/v1/rescues/{case_rep.id}/status", json={"status": "CANCELLED"}, headers=env["token"](env["citizen_reporter"]))
    assert rep_cancel.status_code == 200
    assert rep_cancel.json()["status"] == "CANCELLED"

    # 2. Rescuer: unrelated rescuer denied (403), assigned rescuer allowed (200)
    resp = client.patch(case_url, json={"status": "RESPONDER_EN_ROUTE"}, headers=env["token"](env["rescuer_unrelated"]))
    assert resp.status_code == 403

    resp = client.patch(case_url, json={"status": "RESPONDER_EN_ROUTE"}, headers=env["token"](env["rescuer_assigned"]))
    assert resp.status_code == 200
    assert resp.json()["status"] == "RESPONDER_EN_ROUTE"

    # Advance status through valid lifecycle to AT_VETERINARY_FACILITY
    assert client.patch(case_url, json={"status": "ANIMAL_LOCATED"}, headers=env["token"](env["rescuer_assigned"])).status_code == 200
    assert client.patch(case_url, json={"status": "RESCUED"}, headers=env["token"](env["rescuer_assigned"])).status_code == 200
    assert client.patch(case_url, json={"status": "TRANSPORTING"}, headers=env["token"](env["rescuer_assigned"])).status_code == 200
    assert client.patch(case_url, json={"status": "AT_VETERINARY_FACILITY"}, headers=env["token"](env["rescuer_assigned"])).status_code == 200

    # 3. Veterinarian: foreign vet denied (403), facility vet allowed (200)
    resp = client.patch(case_url, json={"status": "UNDER_TREATMENT"}, headers=env["token"](env["vet_beta"]))
    assert resp.status_code == 403

    resp = client.patch(case_url, json={"status": "UNDER_TREATMENT"}, headers=env["token"](env["vet_alpha"]))
    assert resp.status_code == 200
    assert resp.json()["status"] == "UNDER_TREATMENT"

    # 4. NGO Admin: cross-tenant denied (403), null-org denied (403), own-tenant allowed (200)
    resp = client.patch(case_url, json={"status": "RECOVERING"}, headers=env["token"](env["admin_beta"]))
    assert resp.status_code == 403

    resp = client.patch(case_url, json={"status": "RECOVERING"}, headers=env["token"](env["admin_null_org"]))
    assert resp.status_code == 403

    resp = client.patch(case_url, json={"status": "RECOVERING"}, headers=env["token"](env["admin_alpha"]))
    assert resp.status_code == 200
    assert resp.json()["status"] == "RECOVERING"

    # 5. Super Admin: global access allowed (200)
    resp = client.patch(case_url, json={"status": "CLOSED"}, headers=env["token"](env["super_admin"]))
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLOSED"

    # 6. Unassigned case: NGO Admin cannot update status without claiming first (403)
    unassigned_url = f"/api/v1/rescues/{env['case_unassigned'].id}/status"
    resp = client.patch(unassigned_url, json={"status": "CANCELLED"}, headers=env["token"](env["admin_alpha"]))
    assert resp.status_code == 403


def test_treatment_authorization_and_scoping(client: TestClient, db, auth_env):
    """Verify treatment read and write authorization boundaries."""
    env = auth_env
    case_alpha = env["case_alpha"]
    case_unassigned = env["case_unassigned"]

    # 1. POST treatments on unassigned case (null facility) -> 403 Forbidden
    resp = client.post(
        f"/api/v1/rescues/{case_unassigned.id}/treatments",
        json={"diagnosis": "Test", "treatment_notes": "Checkup", "facility_id": str(env["fac_1"].id)},
        headers=env["token"](env["vet_alpha"]),
    )
    assert resp.status_code == 403
    # Verify facility was NOT auto-assigned to case
    db.refresh(case_unassigned)
    assert case_unassigned.veterinary_facility_id is None

    # Transition case_alpha to AT_VETERINARY_FACILITY so treatment can be administered
    case_alpha.status = RescueStatus.AT_VETERINARY_FACILITY
    db.commit()

    # 2. POST treatments on case_alpha by foreign vet -> 403 Forbidden
    resp = client.post(
        f"/api/v1/rescues/{case_alpha.id}/treatments",
        json={"diagnosis": "Foreign vet test", "treatment_notes": "Checkup", "facility_id": str(env["fac_2"].id)},
        headers=env["token"](env["vet_beta"]),
    )
    assert resp.status_code == 403

    # 3. POST treatments on case_alpha by matching vet -> 200 OK
    resp = client.post(
        f"/api/v1/rescues/{case_alpha.id}/treatments",
        json={
            "diagnosis": "Forelimb fracture stabilized",
            "treatment_notes": "Splint applied",
            "medications": "Meloxicam",
            "facility_id": str(env["fac_1"].id),
        },
        headers=env["token"](env["vet_alpha"]),
    )
    assert resp.status_code == 200

    # 4. GET treatments access matrix
    treatments_url = f"/api/v1/rescues/{case_alpha.id}/treatments"

    # Super admin: 200
    assert client.get(treatments_url, headers=env["token"](env["super_admin"])).status_code == 200
    # Own-tenant NGO: 200
    assert client.get(treatments_url, headers=env["token"](env["admin_alpha"])).status_code == 200
    # Cross-tenant NGO: 403
    assert client.get(treatments_url, headers=env["token"](env["admin_beta"])).status_code == 403
    # Assigned rescuer: 200
    assert client.get(treatments_url, headers=env["token"](env["rescuer_assigned"])).status_code == 200
    # Unrelated rescuer: 403
    assert client.get(treatments_url, headers=env["token"](env["rescuer_unrelated"])).status_code == 403
    # Facility vet: 200
    assert client.get(treatments_url, headers=env["token"](env["vet_alpha"])).status_code == 200
    # Foreign vet: 403
    assert client.get(treatments_url, headers=env["token"](env["vet_beta"])).status_code == 403


def test_animal_record_bola_closure(client: TestClient, db, auth_env):
    """Verify BOLA closure and separated READ vs UPDATE authorization on /api/v1/animals/{animal_id}."""
    env = auth_env
    animal_id = env["animal_alpha"].id
    url = f"/api/v1/animals/{animal_id}"

    # 1. READ Matrix on Linked Animal
    # - Citizen role denied (403)
    assert client.get(url, headers=env["token"](env["citizen_reporter"])).status_code == 403
    # - Unrelated rescuer denied (403)
    assert client.get(url, headers=env["token"](env["rescuer_unrelated"])).status_code == 403
    # - Foreign NGO Beta denied (403)
    assert client.get(url, headers=env["token"](env["admin_beta"])).status_code == 403
    # - Foreign Vet Beta denied (403)
    assert client.get(url, headers=env["token"](env["vet_beta"])).status_code == 403
    # - Assigned rescuer allowed (200)
    assert client.get(url, headers=env["token"](env["rescuer_assigned"])).status_code == 200
    # - Exact-facility Vet Alpha allowed (200)
    assert client.get(url, headers=env["token"](env["vet_alpha"])).status_code == 200
    # - Own-tenant NGO Admin allowed (200)
    assert client.get(url, headers=env["token"](env["admin_alpha"])).status_code == 200
    # - Super Admin allowed (200)
    assert client.get(url, headers=env["token"](env["super_admin"])).status_code == 200

    # 2. UPDATE Matrix on Linked Animal (Stronger Mutation Policy)
    # - Assigned responder PATCH -> 403 (Responders have READ ONLY access to animal records)
    assert client.patch(url, json={"description": "Hacked by Rescuer"}, headers=env["token"](env["rescuer_assigned"])).status_code == 403
    # - Unrelated responder PATCH -> 403
    assert client.patch(url, json={"description": "Hacked by Unrelated"}, headers=env["token"](env["rescuer_unrelated"])).status_code == 403
    # - Citizen PATCH -> 403
    assert client.patch(url, json={"description": "Hacked by Citizen"}, headers=env["token"](env["citizen_reporter"])).status_code == 403
    # - Foreign NGO Beta PATCH -> 403
    assert client.patch(url, json={"description": "Hacked by Foreign NGO"}, headers=env["token"](env["admin_beta"])).status_code == 403
    # - Foreign Vet Beta PATCH -> 403
    assert client.patch(url, json={"description": "Hacked by Foreign Vet"}, headers=env["token"](env["vet_beta"])).status_code == 403

    # - Own-tenant NGO PATCH -> 200
    patch_ngo = client.patch(url, json={"description": "Bruno NGO Updated"}, headers=env["token"](env["admin_alpha"]))
    assert patch_ngo.status_code == 200
    assert patch_ngo.json()["description"] == "Bruno NGO Updated"

    # - Exact-facility veterinarian PATCH:
    # If case is still in dispatch status before arriving at clinic -> 403
    # (case_alpha is currently in RESPONDER_ASSIGNED in auth_env)
    assert client.patch(url, json={"description": "Premature Vet Edit"}, headers=env["token"](env["vet_alpha"])).status_code == 403

    # Transition case_alpha to AT_VETERINARY_FACILITY -> 200
    env["case_alpha"].status = RescueStatus.AT_VETERINARY_FACILITY
    db.commit()
    patch_vet = client.patch(url, json={"description": "Bruno Vet Updated"}, headers=env["token"](env["vet_alpha"]))
    assert patch_vet.status_code == 200
    assert patch_vet.json()["description"] == "Bruno Vet Updated"

    # - Super Admin PATCH -> 200
    patch_super = client.patch(url, json={"description": "Bruno Super Updated"}, headers=env["token"](env["super_admin"]))
    assert patch_super.status_code == 200
    assert patch_super.json()["description"] == "Bruno Super Updated"

    # 3. Standalone / unlinked animal record (no rescue cases linked)
    animal_unlinked = Animal(species="Parrot", description="Standalone Polly")
    db.add(animal_unlinked)
    db.commit()
    db.refresh(animal_unlinked)
    unlinked_url = f"/api/v1/animals/{animal_unlinked.id}"

    # - unlinked animal + NGO admin => 403
    assert client.get(unlinked_url, headers=env["token"](env["admin_alpha"])).status_code == 403
    assert client.patch(unlinked_url, json={"description": "Hacked"}, headers=env["token"](env["admin_alpha"])).status_code == 403
    # - unlinked animal + veterinarian => 403
    assert client.get(unlinked_url, headers=env["token"](env["vet_alpha"])).status_code == 403
    assert client.patch(unlinked_url, json={"description": "Hacked"}, headers=env["token"](env["vet_alpha"])).status_code == 403
    # - unlinked animal + rescuer => 403
    assert client.get(unlinked_url, headers=env["token"](env["rescuer_assigned"])).status_code == 403
    assert client.patch(unlinked_url, json={"description": "Hacked"}, headers=env["token"](env["rescuer_assigned"])).status_code == 403
    # - unlinked animal + citizen => 403
    assert client.get(unlinked_url, headers=env["token"](env["citizen_reporter"])).status_code == 403
    assert client.patch(unlinked_url, json={"description": "Hacked"}, headers=env["token"](env["citizen_reporter"])).status_code == 403
    # - unlinked animal + superadmin => 200
    assert client.get(unlinked_url, headers=env["token"](env["super_admin"])).status_code == 200
    patch_super_unlinked = client.patch(unlinked_url, json={"description": "Polly Managed"}, headers=env["token"](env["super_admin"]))
    assert patch_super_unlinked.status_code == 200
    assert patch_super_unlinked.json()["description"] == "Polly Managed"

    # 4. POST /api/v1/animals (standalone creation restricted to SUPER_ADMIN)
    assert client.post("/api/v1/animals", json={"species": "Rabbit"}, headers=env["token"](env["admin_alpha"])).status_code == 403
    assert client.post("/api/v1/animals", json={"species": "Rabbit"}, headers=env["token"](env["vet_alpha"])).status_code == 403
    assert client.post("/api/v1/animals", json={"species": "Rabbit"}, headers=env["token"](env["rescuer_assigned"])).status_code == 403
    post_super = client.post("/api/v1/animals", json={"species": "Rabbit"}, headers=env["token"](env["super_admin"]))
    assert post_super.status_code == 200
    assert post_super.json()["species"] == "Rabbit"


def test_ngo_admin_null_org_fail_closed(client: TestClient, auth_env):
    """Verify that NGO admin with organization_id=None fails closed (HTTP 403) across all endpoints."""
    env = auth_env
    headers = env["token"](env["admin_null_org"])

    endpoints = [
        ("GET", "/api/v1/ngo/analytics/overview"),
        ("GET", "/api/v1/ngo/analytics/response-times"),
        ("GET", "/api/v1/ngo/analytics/outcomes"),
        ("GET", "/api/v1/ngo/analytics/hotspots"),
        ("GET", "/api/v1/ngo/analytics/insights"),
        ("GET", "/api/v1/ngo/cases"),
        ("GET", "/api/v1/ngo/responders"),
        ("GET", "/api/v1/ngo/veterinary"),
        ("GET", "/api/v1/ngo/organization"),
        ("GET", "/api/v1/ngo/settings/dispatch"),
    ]

    for method, path in endpoints:
        if method == "GET":
            resp = client.get(path, headers=headers)
        else:
            resp = client.post(path, headers=headers)
        assert resp.status_code == 403, f"{method} {path} returned HTTP {resp.status_code}, expected 403"


def test_ngo_analytics_strictly_exclude_unassigned_cases(client: TestClient, auth_env):
    """Verify that NGO analytics query only includes own-tenant claimed cases, excluding unassigned ones."""
    env = auth_env
    headers = env["token"](env["admin_alpha"])

    resp = client.get("/api/v1/ngo/analytics/overview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # There is exactly 1 case claimed by Org Alpha (case_alpha) and 1 unassigned case (case_unassigned).
    # Overview must count strictly 1 case!
    assert data["total_cases"] == 1


def test_ngo_case_action_explicit_claim_only(client: TestClient, db, auth_env):
    """Verify execute_ngo_case_action rejects unassigned cases and does not silently claim them."""
    env = auth_env
    case_unassigned = env["case_unassigned"]
    headers = env["token"](env["admin_alpha"])

    # Attempting action on unassigned case without prior claim -> 403 Forbidden
    resp = client.post(
        f"/api/v1/ngo/cases/{case_unassigned.id}/actions",
        json={"action": "re_dispatch", "reason": "Test unassigned action"},
        headers=headers,
    )
    assert resp.status_code == 403
    db.refresh(case_unassigned)
    assert case_unassigned.organization_id is None, "Case was silently auto-claimed!"

    # Explicit claim operation -> 200 OK
    claim_resp = client.post(
        f"/api/v1/ngo/cases/{case_unassigned.id}/claim",
        headers=headers,
    )
    assert claim_resp.status_code == 200
    db.refresh(case_unassigned)
    assert case_unassigned.organization_id == env["org_alpha"].id

    # Subsequent action on claimed case -> 200 OK
    action_resp = client.post(
        f"/api/v1/ngo/cases/{case_unassigned.id}/actions",
        json={"action": "mark_unresolved", "reason": "Explicitly claimed"},
        headers=headers,
    )
    assert action_resp.status_code == 200


def test_ngo_assign_responder_blocks_unaffiliated_and_foreign(client: TestClient, auth_env):
    """Verify assign_responder action blocks unaffiliated, foreign, and inactive responders."""
    env = auth_env
    case_id = env["case_alpha"].id
    headers = env["token"](env["admin_alpha"])
    action_url = f"/api/v1/ngo/cases/{case_id}/actions"

    # 1. Unaffiliated responder (null org) -> 403 Forbidden
    resp = client.post(
        action_url,
        json={"action": "assign_responder", "rescuer_id": str(env["rescuer_unaffiliated"].id)},
        headers=headers,
    )
    assert resp.status_code == 403

    # 2. Foreign responder (Org Beta) -> 403 Forbidden
    resp = client.post(
        action_url,
        json={"action": "assign_responder", "rescuer_id": str(env["rescuer_foreign"].id)},
        headers=headers,
    )
    assert resp.status_code == 403

    # 3. Inactive own responder -> 400 Bad Request
    resp = client.post(
        action_url,
        json={"action": "assign_responder", "rescuer_id": str(env["rescuer_inactive"].id)},
        headers=headers,
    )
    assert resp.status_code == 400

    # 4. Active own-tenant responder -> 200 OK
    resp = client.post(
        action_url,
        json={"action": "assign_responder", "rescuer_id": str(env["rescuer_unrelated"].id)},
        headers=headers,
    )
    assert resp.status_code == 200
