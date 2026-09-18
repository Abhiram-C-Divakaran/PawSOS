"""Phase 2.9D - Access-Control & Private Media Security Regression Suite.

Verifies:
1. Rescuer access control:
   - Unrelated rescuer cannot access private case detail (403)
   - Unrelated rescuer cannot access evidence access endpoint (403)
   - Case status being 'open' does NOT grant private case or evidence access
   - Assigned rescuer (ACCEPTED) can access case and evidence (200)
   - Rescuer with active, unexpired dispatch offer can access case and evidence (200)
   - Rescuer with expired dispatch offer is denied (403)
   - Responder discovery (/nearby) returns discovery information with empty images ([]),
     never leaking private S3 presigned URLs.
2. Veterinarian access control (Fail-closed facility scoping):
   - Vet assigned to matching facility can access eligible veterinary case and evidence (200)
   - Vet assigned to another facility is denied (403)
   - Vet with veterinary_facility_id=None is denied (403)
   - Case with veterinary_facility_id=None is denied to ordinary vet (403)
   - Vet inbox GET /api/v1/veterinary/cases fails closed when veterinary_facility_id=None (403)
   - Knowledge of case UUID does not bypass facility scoping.
3. NGO tenant isolation (Fail-closed):
   - Own-tenant NGO admin can access eligible case and evidence (200)
   - Cross-tenant NGO admin is denied case and evidence (403)
   - NGO admin with organization_id=None cannot retrieve private evidence (403)
   - Case with organization_id=None does not implicitly expose private evidence (403)
4. Citizen ownership isolation:
   - Reporter can access their own case and evidence (200)
   - Unrelated citizen is denied (403)
5. Super Admin global jurisdiction:
   - Super admin has global administrative access (200)
6. Private media architecture & URL leakage prevention (Section 9):
   - Database stores canonical keys (rescues/uuid.jpg), never presigned query tokens
   - Presigned URLs are temporary and generated ONLY via authorized access endpoint
   - Discovery/list endpoints (/nearby, /my, /ngo/cases, /veterinary/cases, /{case_id})
     do NOT leak presigned AWS tokens (X-Amz-Signature, X-Amz-Credential, etc.).
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.models.user import User
from app.models.rescue_case import RescueCase
from app.models.animal_image import AnimalImage
from app.models.organization import Organization
from app.models.veterinary_facility import VeterinaryFacility
from app.models.rescue_assignment import RescueAssignment
from app.core.constants import UserRole, RescueStatus, AssignmentStatus, OrganizationType
from app.core.security import get_password_hash, create_access_token


@pytest.fixture
def access_test_env(db):
    """Setup isolated multi-tenant entities for access-control testing."""
    # Organizations
    org_1 = Organization(
        name="Org Alpha",
        organization_type=OrganizationType.NGO,
        email="alpha@test.org",
    )
    org_2 = Organization(
        name="Org Beta",
        organization_type=OrganizationType.NGO,
        email="beta@test.org",
    )
    db.add_all([org_1, org_2])
    db.commit()

    # Veterinary Facilities
    fac_1 = VeterinaryFacility(
        name="Clinic Alpha",
        phone="+914841111111",
        latitude=9.9816,
        longitude=76.2999,
        organization_id=org_1.id,
        is_verified=True,
    )
    fac_2 = VeterinaryFacility(
        name="Clinic Beta",
        phone="+914842222222",
        latitude=9.9850,
        longitude=76.3050,
        organization_id=org_2.id,
        is_verified=True,
    )
    db.add_all([fac_1, fac_2])
    db.commit()

    # Users
    reporter = User(
        full_name="Citizen Reporter",
        email=f"reporter_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.CITIZEN,
        is_active=True,
    )
    unrelated_citizen = User(
        full_name="Unrelated Citizen",
        email=f"citizen2_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.CITIZEN,
        is_active=True,
    )
    assigned_rescuer = User(
        full_name="Assigned Rescuer",
        email=f"rescuer1_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.RESCUER,
        is_active=True,
    )
    unassigned_rescuer = User(
        full_name="Unassigned Rescuer",
        email=f"rescuer2_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.RESCUER,
        is_active=True,
    )
    offered_rescuer = User(
        full_name="Offered Rescuer",
        email=f"rescuer3_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.RESCUER,
        is_active=True,
    )
    expired_rescuer = User(
        full_name="Expired Offer Rescuer",
        email=f"rescuer4_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.RESCUER,
        is_active=True,
    )
    ngo_admin_1 = User(
        full_name="NGO Admin Alpha",
        email=f"ngo1_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.NGO_ADMIN,
        organization_id=org_1.id,
        is_active=True,
    )
    ngo_admin_2 = User(
        full_name="NGO Admin Beta",
        email=f"ngo2_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.NGO_ADMIN,
        organization_id=org_2.id,
        is_active=True,
    )
    ngo_admin_no_org = User(
        full_name="NGO Admin No Org",
        email=f"ngo_none_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.NGO_ADMIN,
        organization_id=None,
        is_active=True,
    )
    vet_fac_1 = User(
        full_name="Dr. Alpha",
        email=f"vet1_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.VETERINARIAN,
        veterinary_facility_id=fac_1.id,
        is_active=True,
    )
    vet_fac_2 = User(
        full_name="Dr. Beta",
        email=f"vet2_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.VETERINARIAN,
        veterinary_facility_id=fac_2.id,
        is_active=True,
    )
    vet_no_fac = User(
        full_name="Dr. No Facility",
        email=f"vet_none_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.VETERINARIAN,
        veterinary_facility_id=None,
        is_active=True,
    )
    super_admin = User(
        full_name="Super Admin",
        email=f"super_{uuid.uuid4().hex[:6]}@test.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass"),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )

    all_users = [
        reporter, unrelated_citizen, assigned_rescuer, unassigned_rescuer,
        offered_rescuer, expired_rescuer, ngo_admin_1, ngo_admin_2,
        ngo_admin_no_org, vet_fac_1, vet_fac_2, vet_no_fac, super_admin,
    ]
    db.add_all(all_users)
    db.commit()

    # Create Case A: assigned to org_1, fac_1, under treatment
    case_a = RescueCase(
        case_number=f"PR-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=reporter.id,
        organization_id=org_1.id,
        veterinary_facility_id=fac_1.id,
        status=RescueStatus.UNDER_TREATMENT,
        species="Dog",
        description="Fractured leg",
        latitude=9.9816,
        longitude=76.2999,
        location="POINT(76.2999 9.9816)",
        triage_score=80,
    )
    db.add(case_a)
    db.commit()
    db.refresh(case_a)

    # Add evidence image
    canonical_key = f"rescues/{uuid.uuid4().hex}.jpg"
    image_a = AnimalImage(
        rescue_case_id=case_a.id,
        image_url=canonical_key,
        image_type="primary",
    )
    db.add(image_a)

    # Active accepted assignment for assigned_rescuer
    assign_acc = RescueAssignment(
        rescue_case_id=case_a.id,
        rescuer_id=assigned_rescuer.id,
        assignment_status=AssignmentStatus.ACCEPTED,
        accepted_at=datetime.now(timezone.utc),
    )
    # Active unexpired offer for offered_rescuer
    assign_offer = RescueAssignment(
        rescue_case_id=case_a.id,
        rescuer_id=offered_rescuer.id,
        assignment_status=AssignmentStatus.PENDING,
        offered_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    # Expired offer for expired_rescuer
    assign_expired = RescueAssignment(
        rescue_case_id=case_a.id,
        rescuer_id=expired_rescuer.id,
        assignment_status=AssignmentStatus.PENDING,
        offered_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db.add_all([assign_acc, assign_offer, assign_expired])
    db.commit()

    # Case B: Open / Searching case with NO org and NO facility
    case_b_open = RescueCase(
        case_number=f"PR-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=reporter.id,
        organization_id=None,
        veterinary_facility_id=None,
        status=RescueStatus.SEARCHING_RESPONDER,
        species="Cat",
        description="Stranded kitten",
        latitude=9.9820,
        longitude=76.3000,
        location="POINT(76.3000 9.9820)",
        triage_score=60,
    )
    db.add(case_b_open)
    db.commit()
    db.refresh(case_b_open)

    image_b = AnimalImage(
        rescue_case_id=case_b_open.id,
        image_url=f"rescues/{uuid.uuid4().hex}.jpg",
        image_type="primary",
    )
    db.add(image_b)
    db.commit()

    return {
        "org_1": org_1,
        "org_2": org_2,
        "fac_1": fac_1,
        "fac_2": fac_2,
        "case_a": case_a,
        "image_a": image_a,
        "case_b_open": case_b_open,
        "image_b": image_b,
        "reporter": reporter,
        "unrelated_citizen": unrelated_citizen,
        "assigned_rescuer": assigned_rescuer,
        "unassigned_rescuer": unassigned_rescuer,
        "offered_rescuer": offered_rescuer,
        "expired_rescuer": expired_rescuer,
        "ngo_admin_1": ngo_admin_1,
        "ngo_admin_2": ngo_admin_2,
        "ngo_admin_no_org": ngo_admin_no_org,
        "vet_fac_1": vet_fac_1,
        "vet_fac_2": vet_fac_2,
        "vet_no_fac": vet_no_fac,
        "super_admin": super_admin,
    }


def assert_no_presigned_url_leak(data, context=""):
    """Assert response payload does NOT leak private presigned query parameters or credentials."""
    serialized = str(data)
    forbidden_tokens = [
        "X-Amz-Signature",
        "X-Amz-Credential",
        "X-Amz-Algorithm",
        "X-Amz-Date",
        "X-Amz-Security-Token",
        "AWSAccessKeyId=",
        "Signature=",
    ]
    for token in forbidden_tokens:
        assert token not in serialized, f"Private S3 presigned token '{token}' leaked in {context}"


# ==============================================================================
# SECTION 1: RESCUER ACCESS CONTROL
# ==============================================================================

def test_unrelated_rescuer_cannot_access_private_case_detail(client: TestClient, access_test_env):
    """Unrelated rescuer without assignment or active offer cannot access private case detail."""
    ctx = access_test_env
    token = create_access_token(ctx["unassigned_rescuer"].id)
    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_unrelated_rescuer_cannot_access_case_evidence(client: TestClient, access_test_env):
    """Unrelated rescuer cannot access dedicated evidence image access endpoint."""
    ctx = access_test_env
    token = create_access_token(ctx["unassigned_rescuer"].id)
    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_open_case_status_does_not_grant_private_access_to_rescuer(client: TestClient, access_test_env):
    """Merely having an 'open' or 'searching' case status does NOT grant private case access."""
    ctx = access_test_env
    token = create_access_token(ctx["unassigned_rescuer"].id)
    # Case B is in SEARCHING_RESPONDER status
    resp = client.get(
        f"/api/v1/rescues/{ctx['case_b_open'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403

    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_b_open'].id}/images/{ctx['image_b'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 403


def test_assigned_rescuer_can_access_case_detail_and_evidence(client: TestClient, access_test_env):
    """Assigned rescuer with ACCEPTED assignment can access private case detail and evidence."""
    ctx = access_test_env
    token = create_access_token(ctx["assigned_rescuer"].id)

    # Case detail
    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == str(ctx["case_a"].id)
    assert_no_presigned_url_leak(resp.json(), context="assigned rescuer case detail")

    # Evidence access
    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 200
    assert "url" in resp_img.json()
    assert resp_img.json()["expires_in"] == settings.S3_PRESIGNED_URL_EXPIRE_SECONDS


def test_rescuer_with_active_offer_can_access_case_and_evidence(client: TestClient, access_test_env):
    """Rescuer with a valid, active (unexpired) dispatch offer can access case and evidence."""
    ctx = access_test_env
    token = create_access_token(ctx["offered_rescuer"].id)

    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 200
    assert "url" in resp_img.json()


def test_rescuer_with_expired_offer_is_denied(client: TestClient, access_test_env):
    """Rescuer with expired dispatch offer is strictly denied access (403)."""
    ctx = access_test_env
    token = create_access_token(ctx["expired_rescuer"].id)

    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403

    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 403


def test_nearby_discovery_omits_evidence_images_and_leaks_no_signed_urls(client: TestClient, access_test_env):
    """Responder /nearby discovery endpoint exposes operational data but omits sensitive images."""
    ctx = access_test_env
    token = create_access_token(ctx["unassigned_rescuer"].id)

    resp = client.get(
        "/api/v1/rescues/nearby?lat=9.9816&lng=76.2999&radius_km=10.0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    cases = resp.json()
    assert len(cases) >= 1

    for c in cases:
        # Sensitive evidence is omitted in discovery views
        assert c.get("images") in (None, []), f"Evidence images must be omitted or empty in discovery listing for case {c['id']}"
        assert_no_presigned_url_leak(c, context="nearby discovery item")


# ==============================================================================
# SECTION 2: VETERINARIAN ACCESS CONTROL (FAIL-CLOSED)
# ==============================================================================

def test_veterinarian_assigned_to_matching_facility_can_access(client: TestClient, access_test_env):
    """Vet assigned to matching facility can access eligible veterinary case and evidence."""
    ctx = access_test_env
    token = create_access_token(ctx["vet_fac_1"].id)

    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert_no_presigned_url_leak(resp.json(), context="vet case detail")

    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 200
    assert "url" in resp_img.json()


def test_veterinarian_from_different_facility_is_denied(client: TestClient, access_test_env):
    """Vet from different veterinary facility is denied access (403)."""
    ctx = access_test_env
    token = create_access_token(ctx["vet_fac_2"].id)

    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403

    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 403


def test_veterinarian_with_no_facility_id_is_denied(client: TestClient, access_test_env):
    """Vet with veterinary_facility_id=None fails closed and is denied access (403)."""
    ctx = access_test_env
    token = create_access_token(ctx["vet_no_fac"].id)

    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403

    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 403


def test_case_with_null_facility_id_is_denied_to_veterinarian(client: TestClient, access_test_env):
    """Case with veterinary_facility_id=None fails closed and is denied to ordinary vet (403)."""
    ctx = access_test_env
    token = create_access_token(ctx["vet_fac_1"].id)

    # Case B has veterinary_facility_id=None
    resp = client.get(
        f"/api/v1/rescues/{ctx['case_b_open'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_veterinary_inbox_fails_closed_when_facility_id_none(client: TestClient, access_test_env):
    """Vet inbox GET /api/v1/veterinary/cases fails closed when user has no facility (403)."""
    ctx = access_test_env
    token = create_access_token(ctx["vet_no_fac"].id)

    resp = client.get(
        "/api/v1/veterinary/cases",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ==============================================================================
# SECTION 3: NGO TENANT ISOLATION (FAIL-CLOSED)
# ==============================================================================

def test_own_tenant_ngo_admin_can_access_case_and_evidence(client: TestClient, access_test_env):
    """NGO admin can access cases and evidence belonging to their organization."""
    ctx = access_test_env
    token = create_access_token(ctx["ngo_admin_1"].id)

    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert_no_presigned_url_leak(resp.json(), context="NGO case detail")

    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 200
    assert "url" in resp_img.json()


def test_cross_tenant_ngo_admin_is_denied(client: TestClient, access_test_env):
    """Cross-tenant NGO admin cannot access other organization's case or evidence."""
    ctx = access_test_env
    token = create_access_token(ctx["ngo_admin_2"].id)

    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "Cross-tenant access forbidden" in resp.text

    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 403
    assert "Cross-tenant access forbidden" in resp_img.text


def test_ngo_admin_with_null_organization_id_cannot_access_private_evidence(client: TestClient, access_test_env):
    """NGO admin with organization_id=None fails closed and is denied private evidence access."""
    ctx = access_test_env
    token = create_access_token(ctx["ngo_admin_no_org"].id)

    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 403


def test_case_with_null_organization_id_does_not_expose_private_evidence(client: TestClient, access_test_env):
    """Case with organization_id=None does NOT implicitly expose private evidence to NGO admins."""
    ctx = access_test_env
    token = create_access_token(ctx["ngo_admin_1"].id)

    # Case B has organization_id=None
    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_b_open'].id}/images/{ctx['image_b'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 403


# ==============================================================================
# SECTION 4: CITIZEN OWNERSHIP ISOLATION
# ==============================================================================

def test_citizen_reporter_can_access_own_case_and_evidence(client: TestClient, access_test_env):
    """Citizen who reported the rescue can access their case details and evidence."""
    ctx = access_test_env
    token = create_access_token(ctx["reporter"].id)

    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 200


def test_unrelated_citizen_is_denied(client: TestClient, access_test_env):
    """Unrelated citizen cannot access another citizen's case or evidence."""
    ctx = access_test_env
    token = create_access_token(ctx["unrelated_citizen"].id)

    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403

    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 403


# ==============================================================================
# SECTION 5: SUPER ADMIN GLOBAL JURISDICTION
# ==============================================================================

def test_super_admin_can_access_any_case_and_evidence(client: TestClient, access_test_env):
    """Super Admin retains intentional global access across organizations and facilities."""
    ctx = access_test_env
    token = create_access_token(ctx["super_admin"].id)

    resp = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    resp_img = client.get(
        f"/api/v1/rescues/{ctx['case_a'].id}/images/{ctx['image_a'].id}/access",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_img.status_code == 200


# ==============================================================================
# SECTION 6: URL LEAKAGE & CANONICAL STORAGE INVARIANTS (SECTION 9)
# ==============================================================================

def test_database_stores_canonical_key_not_signed_tokens(db, access_test_env):
    """Verify database AnimalImage records store canonical keys without query tokens."""
    ctx = access_test_env
    img = db.query(AnimalImage).filter(AnimalImage.id == ctx["image_a"].id).first()
    assert img is not None
    assert "?" not in img.image_url
    assert "X-Amz" not in img.image_url
    assert img.image_url.startswith("rescues/")


def test_list_and_detail_endpoints_do_not_leak_signed_s3_tokens(client: TestClient, access_test_env):
    """Verify GET /my, GET /ngo/cases, GET /veterinary/cases, and GET /{id} do NOT leak signed media."""
    ctx = access_test_env
    reporter_token = create_access_token(ctx["reporter"].id)
    ngo_token = create_access_token(ctx["ngo_admin_1"].id)
    vet_token = create_access_token(ctx["vet_fac_1"].id)

    # 1. GET /my
    res_my = client.get("/api/v1/rescues/my", headers={"Authorization": f"Bearer {reporter_token}"})
    assert res_my.status_code == 200
    assert_no_presigned_url_leak(res_my.json(), context="GET /rescues/my")

    # 2. GET /ngo/cases
    res_ngo = client.get("/api/v1/ngo/cases", headers={"Authorization": f"Bearer {ngo_token}"})
    assert res_ngo.status_code == 200
    assert_no_presigned_url_leak(res_ngo.json(), context="GET /ngo/cases")

    # 3. GET /veterinary/cases
    res_vet = client.get("/api/v1/veterinary/cases", headers={"Authorization": f"Bearer {vet_token}"})
    assert res_vet.status_code == 200
    assert_no_presigned_url_leak(res_vet.json(), context="GET /veterinary/cases")

    # 4. GET /rescues/{id}
    res_detail = client.get(f"/api/v1/rescues/{ctx['case_a'].id}", headers={"Authorization": f"Bearer {reporter_token}"})
    assert res_detail.status_code == 200
    assert_no_presigned_url_leak(res_detail.json(), context="GET /rescues/{id}")
