import pytest
import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.models.user import User
from app.models.organization import Organization
from app.models.veterinary_facility import VeterinaryFacility
from app.models.rescue_case import RescueCase
from app.models.rescue_assignment import RescueAssignment
from app.models.rescuer_profile import RescuerProfile
from app.models.notification import Notification
from app.core.constants import (
    UserRole,
    RescueStatus,
    RescuePriority,
    RescuerAvailability,
    AssignmentStatus,
    OrganizationType,
)
from app.core.security import get_password_hash, create_access_token
from app.services.dispatch_service import DispatchService
from app.tasks.dispatch_tasks import expire_dispatch_offers_task

# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------
@pytest.fixture
def pilot_env(db):
    pwd = get_password_hash("pilotpass123")

    org = Organization(
        name="Pilot Kerala Animal Rescue",
        organization_type=OrganizationType.NGO,
        phone="+919840000001",
        email="kerala@pawsos.org",
        address="Kochi, Kerala",
        verification_status=True,
    )
    db.add(org)
    db.commit()

    citizen = User(
        full_name="Citizen Reporter",
        email="reporter@pawsos.org",
        phone="+919840000002",
        password_hash=pwd,
        role=UserRole.CITIZEN,
        is_active=True,
        is_verified=True,
    )
    rescuer_1 = User(
        full_name="Rescuer Near",
        email="rescuer1@pawsos.org",
        phone="+919840000003",
        password_hash=pwd,
        role=UserRole.RESCUER,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    rescuer_2 = User(
        full_name="Rescuer Far",
        email="rescuer2@pawsos.org",
        phone="+919840000004",
        password_hash=pwd,
        role=UserRole.RESCUER,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    vet_user = User(
        full_name="Dr. Vet",
        email="drvet@pawsos.org",
        phone="+919840000005",
        password_hash=pwd,
        role=UserRole.VETERINARIAN,
        is_active=True,
        is_verified=True,
    )
    ngo_admin = User(
        full_name="Pilot NGO Admin",
        email="admin@pawsos.org",
        phone="+919840000006",
        password_hash=pwd,
        role=UserRole.NGO_ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    db.add_all([citizen, rescuer_1, rescuer_2, vet_user, ngo_admin])
    db.commit()

    facility = VeterinaryFacility(
        name="Pilot Animal Hospital",
        phone="+919840000007",
        email="hospital@pawsos.org",
        latitude=9.9810,
        longitude=76.2810,
        location="POINT(76.2810 9.9810)",
        address="MG Road, Kochi",
        supports_emergency=True,
        is_24_hours=True,
        is_verified=True,
    )
    db.add(facility)
    db.commit()

    vet_user.veterinary_facility_id = facility.id
    db.commit()

    # Rescuer 1 location ~1.5km from case (9.9800, 76.2800)
    p1 = RescuerProfile(
        user_id=rescuer_1.id,
        availability_status=RescuerAvailability.AVAILABLE,
        latitude=9.9850,
        longitude=76.2850,
        current_location="POINT(76.2850 9.9850)",
        vehicle_available=True,
        last_location_update=datetime.utcnow(),
    )
    # Rescuer 2 location ~8km from case
    p2 = RescuerProfile(
        user_id=rescuer_2.id,
        availability_status=RescuerAvailability.AVAILABLE,
        latitude=10.0400,
        longitude=76.3300,
        current_location="POINT(76.3300 10.0400)",
        vehicle_available=True,
        last_location_update=datetime.utcnow(),
    )
    db.add_all([p1, p2])
    db.commit()

    return {
        "org": org,
        "citizen": citizen,
        "rescuer_1": rescuer_1,
        "rescuer_2": rescuer_2,
        "vet_user": vet_user,
        "ngo_admin": ngo_admin,
        "facility": facility,
        "p1": p1,
        "p2": p2,
    }

# ---------------------------------------------------------------------------
# PILOT SCENARIO 1: Critical Case Full Lifecycle
# ---------------------------------------------------------------------------
def test_pilot_scenario_1_critical_lifecycle(client: TestClient, db, pilot_env):
    citizen = pilot_env["citizen"]
    rescuer = pilot_env["rescuer_1"]
    vet = pilot_env["vet_user"]
    facility = pilot_env["facility"]

    token_citizen = create_access_token(citizen.id)
    token_rescuer = create_access_token(rescuer.id)
    token_vet = create_access_token(vet.id)

    # Step 1: Report Critical Animal
    report_resp = client.post(
        "/api/v1/rescues",
        json={
            "species": "Dog",
            "description": "Dog struck by car, bleeding heavily from leg",
            "latitude": 9.9800,
            "longitude": 76.2800,
            "address_text": "MG Road, Kochi",
            "bleeding": True,
            "can_walk": False,
            "vehicle_accident": True,
        },
        headers={"Authorization": f"Bearer {token_citizen}"},
    )
    assert report_resp.status_code in [200, 201]
    case_data = report_resp.json()
    case_id = case_data["id"]
    assert case_data["triage_priority"] == "CRITICAL"
    assert case_data["status"] == "SEARCHING_RESPONDER"

    # Step 2: Rescuer views inbox and accepts
    inbox_resp = client.get(
        "/api/v1/rescuers/me/offers",
        headers={"Authorization": f"Bearer {token_rescuer}"},
    )
    assert inbox_resp.status_code == 200
    offers = inbox_resp.json()
    assert len(offers) >= 1
    offer_id = next(o["id"] for o in offers if o["rescue_case_id"] == case_id)

    accept_resp = client.post(
        f"/api/v1/rescuers/offers/{offer_id}/accept",
        headers={"Authorization": f"Bearer {token_rescuer}"},
    )
    assert accept_resp.status_code == 200

    # Step 3: Rescuer advances mission: EN_ROUTE -> ANIMAL_LOCATED -> RESCUED -> TRANSPORTING -> AT_FACILITY
    workflow_steps = [
        ("RESPONDER_EN_ROUTE", None),
        ("ANIMAL_LOCATED", None),
        ("RESCUED", None),
        ("TRANSPORTING", str(facility.id)),
        ("AT_VETERINARY_FACILITY", str(facility.id)),
    ]
    for st, fac_id in workflow_steps:
        body = {"status": st, "notes": f"Step {st}"}
        if fac_id:
            body["veterinary_facility_id"] = fac_id
        res = client.patch(
            f"/api/v1/rescues/{case_id}/status",
            json=body,
            headers={"Authorization": f"Bearer {token_rescuer}"},
        )
        assert res.status_code == 200

    # Step 4: Veterinarian records medical treatment
    treat_resp = client.post(
        f"/api/v1/rescues/{case_id}/treatments",
        json={
            "facility_id": str(facility.id),
            "diagnosis": "Severe laceration, clean fracture",
            "treatment_notes": "Splint applied, antibiotics administered",
            "medications": "Amoxicillin, Meloxicam",
        },
        headers={"Authorization": f"Bearer {token_vet}"},
    )
    assert treat_resp.status_code in [200, 201]

    # Step 5: Post-care transitions: RECOVERING -> READY_FOR_RELEASE -> RELEASED -> CLOSED
    for st in ["RECOVERING", "READY_FOR_RELEASE", "RELEASED", "CLOSED"]:
        res = client.patch(
            f"/api/v1/rescues/{case_id}/status",
            json={"status": st, "notes": f"Completed {st}"},
            headers={"Authorization": f"Bearer {token_vet}"},
        )
        assert res.status_code == 200

    # Verify final case status
    db.expire_all()
    case = db.query(RescueCase).filter(RescueCase.id == uuid.UUID(case_id)).first()
    assert case.status == RescueStatus.CLOSED
    assert case.closed_at is not None

# ---------------------------------------------------------------------------
# PILOT SCENARIO 2: Offer Expiration & Deterministic Radius Escalation
# ---------------------------------------------------------------------------
def test_pilot_scenario_2_offer_expiration_and_radius_escalation(db, pilot_env):
    citizen = pilot_env["citizen"]
    r1 = pilot_env["rescuer_1"]
    r2 = pilot_env["rescuer_2"]

    case = RescueCase(
        case_number=f"PR-PILOT2-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=citizen.id,
        species="Cat",
        description="Trapped kitten",
        latitude=9.9800,
        longitude=76.2800,
        triage_score=85,
        triage_priority=RescuePriority.CRITICAL,
        status=RescueStatus.SEARCHING_RESPONDER,
        dispatch_attempt=1,
        dispatch_radius_km=5.0,
    )
    db.add(case)
    db.commit()

    # Wave 1 (5km): Only Rescuer 1 receives offer
    offers_wave1 = DispatchService.dispatch_case(db, case.id)
    assert len(offers_wave1) == 1
    assert offers_wave1[0].rescuer_id == r1.id

    # Expire Wave 1 offer
    offers_wave1[0].expires_at = datetime.utcnow() - timedelta(seconds=15)
    db.commit()

    # Run periodic worker task
    task_res = expire_dispatch_offers_task(db_session=db)
    assert task_res["status"] == "success"
    assert task_res["expired_offers"] >= 1

    # Verify case radius expanded to 10km
    db.refresh(case)
    assert case.dispatch_attempt == 2
    assert case.dispatch_radius_km == 10.0

    # Verify Rescuer 2 received Wave 2 offer at 10km
    r2_offer = db.query(RescueAssignment).filter(
        RescueAssignment.rescue_case_id == case.id,
        RescueAssignment.rescuer_id == r2.id,
    ).first()
    assert r2_offer is not None
    assert r2_offer.assignment_status == AssignmentStatus.PENDING

# ---------------------------------------------------------------------------
# PILOT SCENARIO 3: Responder Exhaustion Transitions to UNRESOLVED
# ---------------------------------------------------------------------------
def test_pilot_scenario_3_responder_exhaustion_unresolved(db, pilot_env):
    citizen = pilot_env["citizen"]

    # Remote case where zero responders exist anywhere nearby
    case = RescueCase(
        case_number=f"PR-REMOTE-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=citizen.id,
        species="Eagle",
        description="Injured bird in remote hills",
        latitude=11.6000,
        longitude=76.0000,
        triage_score=92,
        triage_priority=RescuePriority.CRITICAL,
        status=RescueStatus.SEARCHING_RESPONDER,
        dispatch_attempt=1,
        dispatch_radius_km=5.0,
    )
    db.add(case)
    db.commit()

    # Automatic dispatch should expand through 5, 10, 20, 40km and exhaust
    offers = DispatchService.dispatch_case(db, case.id, auto_escalate=True)
    assert len(offers) == 0

    # Case must automatically transition to UNRESOLVED
    db.refresh(case)
    assert case.status == RescueStatus.UNRESOLVED

    # Admin alert notification must be recorded
    admin_alert = db.query(Notification).filter(
        Notification.type == "DISPATCH_FAILED",
        Notification.rescue_case_id == case.id,
    ).first()
    assert admin_alert is not None
    assert "Unresolved" in admin_alert.title

# ---------------------------------------------------------------------------
# PILOT SCENARIO 4: Concurrent Offer Acceptance Protection (409 Conflict)
# ---------------------------------------------------------------------------
def test_pilot_scenario_4_concurrent_acceptance_protection(client: TestClient, db, pilot_env):
    citizen = pilot_env["citizen"]
    r1 = pilot_env["rescuer_1"]
    r2 = pilot_env["rescuer_2"]

    token_r1 = create_access_token(r1.id)
    token_r2 = create_access_token(r2.id)

    case = RescueCase(
        case_number=f"PR-RACE-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=citizen.id,
        species="Dog",
        description="Race condition test",
        latitude=9.9800,
        longitude=76.2800,
        status=RescueStatus.SEARCHING_RESPONDER,
        triage_priority=RescuePriority.CRITICAL,
        triage_score=90,
    )
    db.add(case)
    db.commit()

    # Create simultaneous pending offers for both responders
    now = datetime.utcnow()
    exp = now + timedelta(minutes=5)
    offer_1 = RescueAssignment(
        rescue_case_id=case.id,
        rescuer_id=r1.id,
        assignment_status=AssignmentStatus.PENDING,
        offered_at=now,
        expires_at=exp,
    )
    offer_2 = RescueAssignment(
        rescue_case_id=case.id,
        rescuer_id=r2.id,
        assignment_status=AssignmentStatus.PENDING,
        offered_at=now,
        expires_at=exp,
    )
    db.add_all([offer_1, offer_2])
    db.commit()

    # Responder 1 accepts first -> Success (200 OK)
    resp1 = client.post(
        f"/api/v1/rescuers/offers/{offer_1.id}/accept",
        headers={"Authorization": f"Bearer {token_r1}"},
    )
    assert resp1.status_code == 200

    # Responder 2 attempts to accept second -> Conflict (409 Conflict)
    resp2 = client.post(
        f"/api/v1/rescuers/offers/{offer_2.id}/accept",
        headers={"Authorization": f"Bearer {token_r2}"},
    )
    assert resp2.status_code == 409
    msg = str(resp2.json()).lower()
    assert "cancelled" in msg or "already" in msg or "conflict" in msg

    # Verify no double assignment occurred
    db.expire_all()
    assigned_count = db.query(RescueAssignment).filter(
        RescueAssignment.rescue_case_id == case.id,
        RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED,
    ).count()
    assert assigned_count == 1

# ---------------------------------------------------------------------------
# PILOT SCENARIO 5: Scoping & Isolation
# ---------------------------------------------------------------------------
def test_pilot_scenario_5_scoping_and_isolation(client: TestClient, db, pilot_env):
    admin = pilot_env["ngo_admin"]
    vet = pilot_env["vet_user"]
    facility = pilot_env["facility"]
    citizen = pilot_env["citizen"]

    # External foreign organization and case
    pwd = get_password_hash("pass123")
    other_org = Organization(
        name="Foreign Org",
        organization_type=OrganizationType.NGO,
        phone="+919890000001",
        email="foreign@org.com",
        verification_status=True,
    )
    db.add(other_org)
    db.commit()

    foreign_case = RescueCase(
        case_number=f"PR-FORG-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=citizen.id,
        species="Cow",
        description="Foreign org case",
        latitude=12.0000,
        longitude=77.0000,
        status=RescueStatus.SEARCHING_RESPONDER,
        triage_priority=RescuePriority.CRITICAL,
        organization_id=other_org.id,
    )
    db.add(foreign_case)
    db.commit()

    admin_token = create_access_token(admin.id)
    vet_token = create_access_token(vet.id)

    # 1. NGO Admin attempting to access foreign case dossier -> 403 Forbidden
    resp_ngo = client.get(
        f"/api/v1/ngo/cases/{foreign_case.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_ngo.status_code == 403
    assert "belongs to another organization" in resp_ngo.json()["detail"].lower()

    # 2. Other clinic facility
    other_fac = VeterinaryFacility(
        name="External Clinic",
        phone="+919890000002",
        email="ext@clinic.com",
        latitude=12.0000,
        longitude=77.0000,
        location="POINT(77.0000 12.0000)",
        address="Bengaluru",
        is_verified=True,
    )
    db.add(other_fac)
    db.commit()

    foreign_case.veterinary_facility_id = other_fac.id
    db.commit()

    # Vet user attempting to record treatment on case assigned to other facility -> 403 Forbidden
    resp_vet = client.post(
        f"/api/v1/rescues/{foreign_case.id}/treatments",
        json={
            "facility_id": str(facility.id),
            "diagnosis": "Unauthorized access",
            "treatment_notes": "Attempted entry",
        },
        headers={"Authorization": f"Bearer {vet_token}"},
    )
    assert resp_vet.status_code == 403
