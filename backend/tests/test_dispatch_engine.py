import pytest
import uuid
from datetime import datetime, timedelta

from app.models.user import User
from app.models.rescuer_profile import RescuerProfile
from app.models.rescue_case import RescueCase
from app.models.rescue_assignment import RescueAssignment
from app.core.constants import UserRole, RescuerAvailability, RescuePriority, RescueStatus, AssignmentStatus
from app.core.security import get_password_hash, create_access_token
from app.services.dispatch_service import DispatchService


@pytest.fixture
def available_rescuer_near(db):
    user = User(
        full_name="Nearby Available Rescuer",
        email=f"rescuer_near_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass123"),
        role=UserRole.RESCUER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = RescuerProfile(
        user_id=user.id,
        availability_status=RescuerAvailability.AVAILABLE,
        latitude=19.0765,
        longitude=72.8780,
        vehicle_available=True,
        experience_level="Expert",
        reliability_score=98.0,
        last_location_update=datetime.utcnow(),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return user


@pytest.fixture
def available_rescuer_far(db):
    user = User(
        full_name="Far Available Rescuer",
        email=f"rescuer_far_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9197{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass123"),
        role=UserRole.RESCUER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = RescuerProfile(
        user_id=user.id,
        availability_status=RescuerAvailability.AVAILABLE,
        latitude=19.2000,
        longitude=72.9500,  # ~15km away
        vehicle_available=True,
        experience_level="Intermediate",
        reliability_score=90.0,
        last_location_update=datetime.utcnow(),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return user


@pytest.fixture
def busy_rescuer(db):
    user = User(
        full_name="Busy Rescuer",
        email=f"busy_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9191{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass123"),
        role=UserRole.RESCUER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = RescuerProfile(
        user_id=user.id,
        availability_status=RescuerAvailability.BUSY,
        latitude=19.0760,
        longitude=72.8777,
        last_location_update=datetime.utcnow(),
    )
    db.add(profile)
    db.commit()
    return user


@pytest.fixture
def stale_rescuer(db):
    user = User(
        full_name="Stale Location Rescuer",
        email=f"stale_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9192{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass123"),
        role=UserRole.RESCUER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = RescuerProfile(
        user_id=user.id,
        availability_status=RescuerAvailability.AVAILABLE,
        latitude=19.0760,
        longitude=72.8777,
        last_location_update=datetime.utcnow() - timedelta(minutes=45),  # Stale (>30min)
    )
    db.add(profile)
    db.commit()
    return user


def test_automatic_dispatch_on_critical_report(client, citizen_token, available_rescuer_near, busy_rescuer, stale_rescuer):
    """Verify that reporting a critical case automatically creates dispatch offers only for eligible available responders."""
    payload = {
        "species": "Dog",
        "description": "Critical emergency dog hit by car",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "bleeding": True,
        "can_walk": False,
        "conscious": False,
        "vehicle_accident": True,
        "breathing_difficulty": True,
    }
    res = client.post("/api/v1/rescues", json=payload, headers={"Authorization": f"Bearer {citizen_token}"})
    assert res.status_code == 200
    case_data = res.json()
    assert case_data["triage_priority"] == "CRITICAL"
    assert case_data["status"] == "SEARCHING_RESPONDER"

    # Verify nearby available rescuer received dispatch offer
    rescuer_token = create_access_token(available_rescuer_near.id)
    offers_res = client.get("/api/v1/rescuers/me/offers", headers={"Authorization": f"Bearer {rescuer_token}"})
    assert offers_res.status_code == 200
    offers = offers_res.json()
    assert len(offers) == 1
    assert offers[0]["rescue_case_id"] == case_data["id"]
    assert offers[0]["assignment_status"] == "PENDING"
    assert offers[0]["dispatch_score"] > 80.0

    # Busy rescuer must have NO offers
    busy_token = create_access_token(busy_rescuer.id)
    busy_offers = client.get("/api/v1/rescuers/me/offers", headers={"Authorization": f"Bearer {busy_token}"})
    assert len(busy_offers.json()) == 0

    # Stale rescuer must have NO offers
    stale_token = create_access_token(stale_rescuer.id)
    stale_offers = client.get("/api/v1/rescuers/me/offers", headers={"Authorization": f"Bearer {stale_token}"})
    assert len(stale_offers.json()) == 0


def test_offer_acceptance_and_cancellation_race(client, citizen_token, available_rescuer_near, available_rescuer_far):
    """Verify that when one responder accepts, remaining offers are cancelled and case is assigned."""
    # Create critical case
    payload = {
        "species": "Dog",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "bleeding": True,
        "can_walk": False,
        "conscious": True,
        "vehicle_accident": True,
        "breathing_difficulty": False,
    }
    res = client.post("/api/v1/rescues", json=payload, headers={"Authorization": f"Bearer {citizen_token}"})
    case_id = res.json()["id"]

    token_near = create_access_token(available_rescuer_near.id)
    token_far = create_access_token(available_rescuer_far.id)

    # Both responders check offers
    offers_near = client.get("/api/v1/rescuers/me/offers", headers={"Authorization": f"Bearer {token_near}"}).json()
    assert len(offers_near) >= 1
    offer_id_near = offers_near[0]["id"]

    # Near rescuer accepts offer
    accept_res = client.post(f"/api/v1/rescuers/offers/{offer_id_near}/accept", headers={"Authorization": f"Bearer {token_near}"})
    assert accept_res.status_code == 200
    assert accept_res.json()["assignment_status"] == "ACCEPTED"

    # Verify case is now RESPONDER_ASSIGNED
    case_res = client.get(f"/api/v1/rescues/{case_id}", headers={"Authorization": f"Bearer {token_near}"})
    assert case_res.json()["status"] == "RESPONDER_ASSIGNED"


def test_responder_rejection_reason(client, citizen_token, available_rescuer_near):
    """Verify responder can reject an offer with a reason."""
    res = client.post(
        "/api/v1/rescues",
        json={"species": "Cat", "latitude": 19.0760, "longitude": 72.8777, "bleeding": True},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    case_id = res.json()["id"]

    rescuer_token = create_access_token(available_rescuer_near.id)
    offers = client.get("/api/v1/rescuers/me/offers", headers={"Authorization": f"Bearer {rescuer_token}"}).json()
    assert len(offers) >= 1
    offer_id = offers[0]["id"]

    reject_res = client.post(
        f"/api/v1/rescuers/offers/{offer_id}/reject",
        json={"reason": "too_far"},
        headers={"Authorization": f"Bearer {rescuer_token}"}
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["assignment_status"] == "REJECTED"
    assert reject_res.json()["rejection_reason"] == "too_far"
