import pytest
import uuid
from datetime import datetime, timedelta
from app.models.user import User
from app.models.rescuer_profile import RescuerProfile
from app.models.rescue_case import RescueCase
from app.models.rescue_assignment import RescueAssignment
from app.models.notification import Notification
from app.core.constants import UserRole, RescueStatus, RescuePriority, RescuerAvailability, AssignmentStatus
from app.core.security import get_password_hash
from app.services.dispatch_service import DispatchService
from app.tasks.dispatch_tasks import expire_dispatch_offers_task
from app.tasks.celery_app import celery_app

# Run Celery in eager mode for deterministic testing
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

@pytest.fixture
def background_dispatch_env(db):
    pwd = get_password_hash("pass123")

    citizen = User(
        full_name="Citizen Tester",
        email="citizen.bg@pawsos.org",
        phone="+919100000001",
        password_hash=pwd,
        role=UserRole.CITIZEN,
        is_active=True,
    )
    admin = User(
        full_name="Admin Tester",
        email="admin.bg@pawsos.org",
        phone="+919100000002",
        password_hash=pwd,
        role=UserRole.NGO_ADMIN,
        is_active=True,
    )
    # Rescuer 1 at ~2.5km
    r1 = User(
        full_name="Rescuer Near",
        email="r1.bg@pawsos.org",
        phone="+919100000003",
        password_hash=pwd,
        role=UserRole.RESCUER,
        is_active=True,
    )
    # Rescuer 2 at ~8km
    r2 = User(
        full_name="Rescuer Mid",
        email="r2.bg@pawsos.org",
        phone="+919100000004",
        password_hash=pwd,
        role=UserRole.RESCUER,
        is_active=True,
    )
    db.add_all([citizen, admin, r1, r2])
    db.commit()

    p1 = RescuerProfile(
        user_id=r1.id,
        availability_status=RescuerAvailability.AVAILABLE,
        latitude=9.9820,
        longitude=76.3000,
        last_location_update=datetime.utcnow(),
    )
    p2 = RescuerProfile(
        user_id=r2.id,
        availability_status=RescuerAvailability.AVAILABLE,
        latitude=10.0400,
        longitude=76.3300,
        last_location_update=datetime.utcnow(),
    )
    db.add_all([p1, p2])
    db.commit()

    return {
        "citizen": citizen,
        "admin": admin,
        "r1": r1,
        "r2": r2,
    }

def test_stale_offer_expiry_and_radius_escalation(db, background_dispatch_env):
    citizen = background_dispatch_env["citizen"]
    r1 = background_dispatch_env["r1"]
    r2 = background_dispatch_env["r2"]

    # Create critical case at (9.9800, 76.2800)
    case = RescueCase(
        case_number=f"PR-BG-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=citizen.id,
        species="Dog",
        description="Dog hit by vehicle",
        latitude=9.9800,
        longitude=76.2800,
        triage_score=90,
        triage_priority=RescuePriority.CRITICAL,
        status=RescueStatus.SEARCHING_RESPONDER,
        dispatch_attempt=1,
        dispatch_radius_km=5.0,
    )
    db.add(case)
    db.commit()

    # Wave 1: initial dispatch creates offer for nearby r1 (< 5km)
    offers = DispatchService.dispatch_case(db, case.id)
    assert len(offers) == 1
    assert offers[0].rescuer_id == r1.id
    assert offers[0].assignment_status == AssignmentStatus.PENDING

    # Fast-forward time: artificially expire the offer
    offers[0].expires_at = datetime.utcnow() - timedelta(seconds=10)
    db.commit()

    # Trigger periodic Celery task
    data = expire_dispatch_offers_task(db_session=db)
    assert data["status"] == "success"
    assert data["expired_offers"] >= 1

    db.refresh(offers[0])
    assert offers[0].assignment_status == AssignmentStatus.EXPIRED

    # Verify radius escalated automatically to 10km and notified r2
    db.refresh(case)
    assert case.dispatch_attempt == 2
    assert case.dispatch_radius_km == 10.0

    # Verify r2 received a pending offer at the new radius
    r2_offer = db.query(RescueAssignment).filter(
        RescueAssignment.rescue_case_id == case.id,
        RescueAssignment.rescuer_id == r2.id,
    ).first()
    assert r2_offer is not None
    assert r2_offer.assignment_status == AssignmentStatus.PENDING

def test_dispatch_exhaustion_transitions_to_unresolved(db, background_dispatch_env):
    citizen = background_dispatch_env["citizen"]

    # Remote case where no responders exist in any radius
    case = RescueCase(
        case_number=f"PR-EXHAUST-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=citizen.id,
        species="Cow",
        description="Isolated rural incident",
        latitude=15.5000,
        longitude=75.5000,
        triage_score=95,
        triage_priority=RescuePriority.CRITICAL,
        status=RescueStatus.SEARCHING_RESPONDER,
        dispatch_attempt=1,
        dispatch_radius_km=5.0,
    )
    db.add(case)
    db.commit()

    # Dispatch should attempt all radius levels (5, 10, 20, 40km) and exhaust
    offers = DispatchService.dispatch_case(db, case.id, auto_escalate=True)
    assert len(offers) == 0

    db.refresh(case)
    assert case.status == RescueStatus.UNRESOLVED

    # Verify admin alert notification was generated
    admin_notif = db.query(Notification).filter(
        Notification.type == "DISPATCH_FAILED",
        Notification.rescue_case_id == case.id,
    ).first()
    assert admin_notif is not None
    assert "Unresolved" in admin_notif.title
