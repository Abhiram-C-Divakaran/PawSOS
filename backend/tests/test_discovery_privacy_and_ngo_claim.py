"""Tests for discovery privacy and NGO case claiming semantics.

Verifies:
1. /rescues/nearby returns RescueDiscoverySummary without private scene or reporter details.
2. /ngo/cases unassigned discovery masks exact address and omits private evidence/reporter details.
3. Explicit NGO case claim endpoint (POST /api/v1/ngo/cases/{case_id}/claim) operates atomically with audit logging.
4. Same-org repeat claim is idempotent (HTTP 200).
5. Cross-tenant claim is rejected (HTTP 409 Conflict).
6. Manual NGO assignment acquires case locks, prevents two active ACCEPTED winners, and cancels other pending offers.
"""

import uuid
from datetime import datetime
import pytest

from app.models.user import User
from app.models.organization import Organization
from app.models.rescue_case import RescueCase
from app.models.rescue_assignment import RescueAssignment
from app.models.rescuer_profile import RescuerProfile
from app.models.animal_image import AnimalImage
from app.models.audit_log import AuditLog
from app.core.constants import UserRole, RescueStatus, AssignmentStatus, RescuePriority, RescuerAvailability, OrganizationType
from app.core.security import get_password_hash, create_access_token


@pytest.fixture
def org_alpha(db):
    org = Organization(
        name="Org Alpha Test",
        organization_type=OrganizationType.NGO,
        email=f"org_alpha_{uuid.uuid4().hex[:6]}@example.com",
        phone="+919876543210",
        address="Marine Drive, Kochi",
        verification_status=True,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def org_beta(db):
    org = Organization(
        name="Org Beta Test",
        organization_type=OrganizationType.NGO,
        email=f"org_beta_{uuid.uuid4().hex[:6]}@example.com",
        phone="+919876543211",
        address="Fort Kochi, Kochi",
        verification_status=True,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def admin_alpha(db, org_alpha):
    user = User(
        full_name="Admin Alpha",
        email=f"admin_a_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.NGO_ADMIN,
        organization_id=org_alpha.id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_beta(db, org_beta):
    user = User(
        full_name="Admin Beta",
        email=f"admin_b_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.NGO_ADMIN,
        organization_id=org_beta.id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def rescuer_alpha(db, org_alpha):
    user = User(
        full_name="Rescuer Alpha",
        email=f"rescuer_a_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.RESCUER,
        organization_id=org_alpha.id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = RescuerProfile(
        user_id=user.id,
        organization_id=org_alpha.id,
        availability_status=RescuerAvailability.AVAILABLE,
        latitude=9.9850,
        longitude=76.2980,
        current_location="POINT(76.2980 9.9850)",
        last_location_update=datetime.utcnow(),
    )
    db.add(profile)
    db.commit()
    return user


@pytest.fixture
def rescuer_alpha_2(db, org_alpha):
    user = User(
        full_name="Rescuer Alpha 2",
        email=f"rescuer_a2_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.RESCUER,
        organization_id=org_alpha.id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = RescuerProfile(
        user_id=user.id,
        organization_id=org_alpha.id,
        availability_status=RescuerAvailability.AVAILABLE,
        latitude=9.9860,
        longitude=76.2990,
        current_location="POINT(76.2990 9.9860)",
        last_location_update=datetime.utcnow(),
    )
    db.add(profile)
    db.commit()
    return user


@pytest.fixture
def citizen_user(db):
    user = User(
        full_name="Citizen Reporter",
        email=f"citizen_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.CITIZEN,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_case_with_evidence(db, citizen_user):
    case = RescueCase(
        case_number=f"CAS-PRIV-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=citizen_user.id,
        species="Canine",
        description="Private description of injured animal at Marine Drive",
        latitude=9.9852,
        longitude=76.2981,
        address_text="House 123, Secret Lane, Marine Drive, Kochi",
        status=RescueStatus.SEARCHING_RESPONDER,
        triage_priority=RescuePriority.CRITICAL,
        triage_score=85,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    img = AnimalImage(
        rescue_case_id=case.id,
        image_url="evidence/private_dog_photo.jpg",
        image_type="INITIAL_REPORT",
    )
    db.add(img)
    db.commit()
    db.refresh(case)
    return case


def test_nearby_rescues_privacy_safe_response(client, rescuer_alpha, sample_case_with_evidence):
    """Ensure GET /rescues/nearby returns RescueDiscoverySummary stripping private scene/reporter details."""
    token = create_access_token(rescuer_alpha.id)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get(
        "/api/v1/rescues/nearby",
        params={"lat": 9.9850, "lng": 76.2980, "radius_km": 15.0},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    item = next(d for d in data if d["id"] == str(sample_case_with_evidence.id))
    # Authorized public discovery fields must exist
    assert item["id"] == str(sample_case_with_evidence.id)
    assert item["case_number"] == sample_case_with_evidence.case_number
    assert item["species"] == "Canine"
    assert item["triage_priority"] == "CRITICAL"
    assert item["status"] == "SEARCHING_RESPONDER"
    assert item["distance_km"] is not None

    # Sensitive fields must NEVER be leaked in nearby discovery
    assert "reporter_id" not in item
    assert "latitude" not in item
    assert "longitude" not in item
    assert "address_text" not in item
    assert "images" not in item
    assert "assigned_responder" not in item
    assert "veterinary_facility_id" not in item
    assert "description" not in item


def test_ngo_unassigned_cases_summary_privacy(client, admin_alpha, sample_case_with_evidence):
    """Ensure GET /ngo/cases returns NGOCaseSummaryResponse masking exact location and omitting evidence keys for unassigned cases."""
    assert sample_case_with_evidence.organization_id is None

    token = create_access_token(admin_alpha.id)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/ngo/cases", headers=headers)
    assert resp.status_code == 200
    cases = resp.json()
    assert len(cases) >= 1

    item = next(c for c in cases if c["id"] == str(sample_case_with_evidence.id))
    # Verified fields
    assert item["case_number"] == sample_case_with_evidence.case_number
    assert item["organization_id"] is None
    # Address must be masked for unassigned case
    assert item["address_text"] == "Location protected until claim"
    # Reporter details and evidence keys must be absent
    assert "reporter_id" not in item
    assert "images" not in item
    assert "latitude" not in item
    assert "longitude" not in item


def test_ngo_case_claim_succeeds_atomically(client, db, admin_alpha, sample_case_with_evidence, org_alpha):
    """Ensure POST /api/v1/ngo/cases/{case_id}/claim assigns organization_id and creates AuditLog."""
    token = create_access_token(admin_alpha.id)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(f"/api/v1/ngo/cases/{sample_case_with_evidence.id}/claim", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["organization_id"] == str(org_alpha.id)

    db.refresh(sample_case_with_evidence)
    assert sample_case_with_evidence.organization_id == org_alpha.id

    # Verify audit log
    audit = db.query(AuditLog).filter(
        AuditLog.entity == "rescue_case",
        AuditLog.entity_id == sample_case_with_evidence.id,
        AuditLog.action == "NGO_CASE_CLAIMED",
    ).first()
    assert audit is not None
    assert audit.actor_id == admin_alpha.id
    assert audit.new_value == {"organization_id": str(org_alpha.id)}


def test_ngo_case_claim_idempotent_same_org(client, admin_alpha, sample_case_with_evidence, org_alpha):
    """Repeat claim by the same organization returns success idempotently."""
    token = create_access_token(admin_alpha.id)
    headers = {"Authorization": f"Bearer {token}"}

    # First claim
    resp1 = client.post(f"/api/v1/ngo/cases/{sample_case_with_evidence.id}/claim", headers=headers)
    assert resp1.status_code == 200

    # Repeat claim
    resp2 = client.post(f"/api/v1/ngo/cases/{sample_case_with_evidence.id}/claim", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["success"] is True


def test_ngo_case_claim_cross_tenant_conflict(client, admin_alpha, admin_beta, sample_case_with_evidence):
    """Claiming a case already owned by another organization fails with HTTP 409 Conflict."""
    token_a = create_access_token(admin_alpha.id)
    token_b = create_access_token(admin_beta.id)

    # Alpha claims first
    resp_a = client.post(
        f"/api/v1/ngo/cases/{sample_case_with_evidence.id}/claim",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_a.status_code == 200

    # Beta attempts to claim owned case
    resp_b = client.post(
        f"/api/v1/ngo/cases/{sample_case_with_evidence.id}/claim",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == 409
    assert "already been claimed" in resp_b.json()["detail"]


def test_manual_assignment_single_winner_locking(client, db, admin_alpha, rescuer_alpha, rescuer_alpha_2, sample_case_with_evidence):
    """Ensure assign_responder cancels competing offers and never creates two active winners."""
    token_admin = create_access_token(admin_alpha.id)
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # Create competing pending offers for Rescuer 1 and Rescuer 2
    offer1 = RescueAssignment(
        rescue_case_id=sample_case_with_evidence.id,
        rescuer_id=rescuer_alpha.id,
        assignment_status=AssignmentStatus.PENDING,
        offered_at=datetime.utcnow(),
    )
    offer2 = RescueAssignment(
        rescue_case_id=sample_case_with_evidence.id,
        rescuer_id=rescuer_alpha_2.id,
        assignment_status=AssignmentStatus.PENDING,
        offered_at=datetime.utcnow(),
    )
    db.add_all([offer1, offer2])
    db.commit()

    # Admin manually assigns Rescuer 1
    resp = client.post(
        f"/api/v1/ngo/cases/{sample_case_with_evidence.id}/actions",
        json={"action": "assign_responder", "rescuer_id": str(rescuer_alpha.id)},
        headers=headers_admin,
    )
    assert resp.status_code == 200

    db.refresh(offer1)
    db.refresh(offer2)

    # Offer 1 must be ACCEPTED, Offer 2 must be CANCELLED
    assert offer1.assignment_status == AssignmentStatus.ACCEPTED
    assert offer2.assignment_status == AssignmentStatus.CANCELLED

    # Check total accepted assignments
    accepted = db.query(RescueAssignment).filter(
        RescueAssignment.rescue_case_id == sample_case_with_evidence.id,
        RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED,
    ).all()
    assert len(accepted) == 1
    assert accepted[0].rescuer_id == rescuer_alpha.id

    # Now reassign to Rescuer 2
    resp_reassign = client.post(
        f"/api/v1/ngo/cases/{sample_case_with_evidence.id}/actions",
        json={"action": "assign_responder", "rescuer_id": str(rescuer_alpha_2.id)},
        headers=headers_admin,
    )
    assert resp_reassign.status_code == 200

    db.refresh(offer1)
    assert offer1.assignment_status == AssignmentStatus.CANCELLED

    accepted_after = db.query(RescueAssignment).filter(
        RescueAssignment.rescue_case_id == sample_case_with_evidence.id,
        RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED,
    ).all()
    assert len(accepted_after) == 1
    assert accepted_after[0].rescuer_id == rescuer_alpha_2.id
