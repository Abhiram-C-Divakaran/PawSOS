"""Tests for dispatch claim authorization and single-winner integrity.

Covers all 12 points required by PawReach Dispatch Claim Integrity Closure:
1. Rescuer with their own active pending offer can accept via canonical endpoint.
2. Rescuer without an offer cannot accept a case by case UUID (403 Forbidden).
3. Rescuer cannot accept another rescuer's offer (404 / 403).
4. Expired offer cannot be accepted (409 Conflict).
5. Cancelled offer cannot be accepted (409 Conflict).
6. Rejected offer cannot later be accepted (409 Conflict).
7. Second concurrent rescuer receives conflict after first winner (409 Conflict).
8. Winning acceptance cancels all other PENDING offers for that case.
9. Direct legacy /rescues/{case_id}/accept shim:
   - delegates to DispatchService.accept_offer
   - requires owned active offer
   - never creates assignment directly
10. Nearby discovery does not grant private case or evidence authorization.
11. Open SEARCHING_RESPONDER status alone does not grant claim authority.
12. UUID knowledge alone does not grant claim authority.
"""
import uuid
from datetime import datetime, timedelta
import pytest

from app.models.user import User
from app.models.rescue_case import RescueCase
from app.models.rescue_assignment import RescueAssignment
from app.models.rescuer_profile import RescuerProfile
from app.models.animal_image import AnimalImage
from app.core.constants import UserRole, RescueStatus, AssignmentStatus, RescuerAvailability
from app.core.security import get_password_hash, create_access_token


@pytest.fixture
def second_rescuer(db):
    """Create a second active responder with profile."""
    user = User(
        full_name="Second Rescuer",
        email=f"rescuer2_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
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
        latitude=19.0770,
        longitude=72.8780,
        current_location="POINT(72.8780 19.0770)",
        last_location_update=datetime.utcnow(),
    )
    db.add(profile)
    db.commit()
    return user


@pytest.fixture
def second_rescuer_token(second_rescuer):
    return create_access_token(second_rescuer.id)


@pytest.fixture
def third_rescuer(db):
    """Create a third rescuer without nearby location (no automatic offer)."""
    user = User(
        full_name="Third Rescuer (Far)",
        email=f"rescuer3_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.RESCUER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def third_rescuer_token(third_rescuer):
    return create_access_token(third_rescuer.id)


class TestDispatchClaimAuthorization:
    """Validate claim authorization and single-winner consistency."""

    def test_rescuer_with_own_active_offer_can_accept(
        self, client, db, citizen_token, rescuer_user, rescuer_token
    ):
        """1. Rescuer with their own active pending offer can accept via canonical endpoint."""
        create_res = client.post(
            "/api/v1/rescues",
            json={"species": "Dog", "latitude": 19.0760, "longitude": 72.8777},
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        assert create_res.status_code == 200
        case_id = create_res.json()["id"]
        case_uuid = uuid.UUID(case_id)

        # Offer was generated for rescuer_user
        offer = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.rescue_case_id == case_uuid,
                RescueAssignment.rescuer_id == rescuer_user.id,
                RescueAssignment.assignment_status == AssignmentStatus.PENDING,
            )
            .first()
        )
        assert offer is not None

        # Accept via canonical offer endpoint
        accept_res = client.post(
            f"/api/v1/rescuers/offers/{offer.id}/accept",
            headers={"Authorization": f"Bearer {rescuer_token}"},
        )
        assert accept_res.status_code == 200
        assert accept_res.json()["assignment_status"] == "ACCEPTED"

    def test_rescuer_without_offer_cannot_accept_by_case_uuid(
        self, client, citizen_token, third_rescuer_token
    ):
        """2. Rescuer without an offer cannot accept a case by case UUID (HTTP 403)."""
        create_res = client.post(
            "/api/v1/rescues",
            json={"species": "Dog", "latitude": 19.0760, "longitude": 72.8777},
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        assert create_res.status_code == 200
        case_id = create_res.json()["id"]

        # third_rescuer has no offer for this case
        accept_res = client.post(
            f"/api/v1/rescues/{case_id}/accept",
            headers={"Authorization": f"Bearer {third_rescuer_token}"},
        )
        assert accept_res.status_code == 403
        assert "No active dispatch offer found" in accept_res.text

    def test_rescuer_cannot_accept_another_rescuers_offer(
        self, client, db, citizen_token, rescuer_user, second_rescuer_token
    ):
        """3. Rescuer cannot accept another rescuer's offer (HTTP 404)."""
        create_res = client.post(
            "/api/v1/rescues",
            json={"species": "Dog", "latitude": 19.0760, "longitude": 72.8777},
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        case_id = create_res.json()["id"]
        case_uuid = uuid.UUID(case_id)

        offer1 = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.rescue_case_id == case_uuid,
                RescueAssignment.rescuer_id == rescuer_user.id,
            )
            .first()
        )
        assert offer1 is not None

        # second_rescuer attempts to accept offer1 belonging to rescuer_user
        res = client.post(
            f"/api/v1/rescuers/offers/{offer1.id}/accept",
            headers={"Authorization": f"Bearer {second_rescuer_token}"},
        )
        assert res.status_code == 404
        assert "not found for this rescuer" in res.text.lower()

    def test_expired_offer_cannot_be_accepted(
        self, client, db, citizen_token, rescuer_user, rescuer_token
    ):
        """4. Expired offer cannot be accepted (HTTP 409 Conflict)."""
        create_res = client.post(
            "/api/v1/rescues",
            json={"species": "Cat", "latitude": 19.0760, "longitude": 72.8777},
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        case_id = create_res.json()["id"]
        case_uuid = uuid.UUID(case_id)

        offer = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.rescue_case_id == case_uuid,
                RescueAssignment.rescuer_id == rescuer_user.id,
            )
            .first()
        )
        assert offer is not None

        # Expire offer manually
        offer.expires_at = datetime.utcnow() - timedelta(seconds=10)
        db.commit()

        # Canonical endpoint rejects
        res = client.post(
            f"/api/v1/rescuers/offers/{offer.id}/accept",
            headers={"Authorization": f"Bearer {rescuer_token}"},
        )
        assert res.status_code == 409
        assert "expired" in res.text.lower()

        # Legacy shim also rejects with 409 Conflict
        res_shim = client.post(
            f"/api/v1/rescues/{case_id}/accept",
            headers={"Authorization": f"Bearer {rescuer_token}"},
        )
        assert res_shim.status_code == 409

    def test_cancelled_offer_cannot_be_accepted(
        self, client, db, citizen_token, rescuer_user, rescuer_token
    ):
        """5. Cancelled offer cannot be accepted (HTTP 409 Conflict)."""
        create_res = client.post(
            "/api/v1/rescues",
            json={"species": "Bird", "latitude": 19.0760, "longitude": 72.8777},
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        case_id = create_res.json()["id"]
        case_uuid = uuid.UUID(case_id)

        offer = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.rescue_case_id == case_uuid,
                RescueAssignment.rescuer_id == rescuer_user.id,
            )
            .first()
        )
        offer.assignment_status = AssignmentStatus.CANCELLED
        db.commit()

        res = client.post(
            f"/api/v1/rescuers/offers/{offer.id}/accept",
            headers={"Authorization": f"Bearer {rescuer_token}"},
        )
        assert res.status_code == 409
        assert "no longer pending" in res.text.lower()

    def test_rejected_offer_cannot_later_be_accepted(
        self, client, db, citizen_token, rescuer_user, rescuer_token
    ):
        """6. Rejected offer cannot later be accepted (HTTP 409 Conflict)."""
        create_res = client.post(
            "/api/v1/rescues",
            json={"species": "Dog", "latitude": 19.0760, "longitude": 72.8777},
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        case_id = create_res.json()["id"]
        case_uuid = uuid.UUID(case_id)

        offer = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.rescue_case_id == case_uuid,
                RescueAssignment.rescuer_id == rescuer_user.id,
            )
            .first()
        )

        # Rescuer declines
        rej = client.post(
            f"/api/v1/rescuers/offers/{offer.id}/reject",
            json={"reason": "Vehicle flat tire"},
            headers={"Authorization": f"Bearer {rescuer_token}"},
        )
        assert rej.status_code == 200

        # Rescuer attempts to accept declined offer
        acc = client.post(
            f"/api/v1/rescuers/offers/{offer.id}/accept",
            headers={"Authorization": f"Bearer {rescuer_token}"},
        )
        assert acc.status_code == 409
        assert "no longer pending" in acc.text.lower()

    def test_second_concurrent_rescuer_receives_conflict_after_first_winner(
        self, client, db, citizen_token, rescuer_user, rescuer_token, second_rescuer, second_rescuer_token
    ):
        """7 & 8. Winning acceptance cancels all other PENDING offers; second rescuer gets 409."""
        create_res = client.post(
            "/api/v1/rescues",
            json={
                "species": "Dog",
                "latitude": 19.0760,
                "longitude": 72.8777,
                "conscious": False,
                "breathing_difficulty": True,
            },
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        case_id = create_res.json()["id"]
        case_uuid = uuid.UUID(case_id)

        # Both rescuers received offers
        offer1 = (
            db.query(RescueAssignment)
            .filter(RescueAssignment.rescue_case_id == case_uuid, RescueAssignment.rescuer_id == rescuer_user.id)
            .first()
        )
        offer2 = (
            db.query(RescueAssignment)
            .filter(RescueAssignment.rescue_case_id == case_uuid, RescueAssignment.rescuer_id == second_rescuer.id)
            .first()
        )
        assert offer1 is not None and offer2 is not None

        # Rescuer 1 accepts
        acc1 = client.post(
            f"/api/v1/rescuers/offers/{offer1.id}/accept",
            headers={"Authorization": f"Bearer {rescuer_token}"},
        )
        assert acc1.status_code == 200

        # Verify Rescuer 2's offer was cancelled in DB
        db.refresh(offer2)
        assert offer2.assignment_status == AssignmentStatus.CANCELLED

        # Rescuer 2 attempts acceptance
        acc2 = client.post(
            f"/api/v1/rescuers/offers/{offer2.id}/accept",
            headers={"Authorization": f"Bearer {second_rescuer_token}"},
        )
        assert acc2.status_code == 409

    def test_legacy_accept_shim_delegates_and_never_creates_assignment_directly(
        self, client, db, citizen_token, rescuer_user, rescuer_token
    ):
        """9. Legacy /rescues/{case_id}/accept shim delegates to DispatchService.accept_offer."""
        create_res = client.post(
            "/api/v1/rescues",
            json={"species": "Dog", "latitude": 19.0760, "longitude": 72.8777},
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        case_id = create_res.json()["id"]
        case_uuid = uuid.UUID(case_id)

        assignment_count_before = (
            db.query(RescueAssignment).filter(RescueAssignment.rescue_case_id == case_uuid).count()
        )

        # Call legacy endpoint
        acc = client.post(
            f"/api/v1/rescues/{case_id}/accept",
            headers={"Authorization": f"Bearer {rescuer_token}"},
        )
        assert acc.status_code == 200
        assert acc.json()["success"] is True

        # Ensure NO duplicate assignment was created
        assignment_count_after = (
            db.query(RescueAssignment).filter(RescueAssignment.rescue_case_id == case_uuid).count()
        )
        assert assignment_count_after == assignment_count_before

        accepted = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.rescue_case_id == case_uuid,
                RescueAssignment.rescuer_id == rescuer_user.id,
            )
            .first()
        )
        assert accepted.assignment_status == AssignmentStatus.ACCEPTED

    def test_nearby_discovery_does_not_grant_private_case_or_evidence_access(
        self, client, db, citizen_token, third_rescuer_token
    ):
        """10. Nearby discovery does not grant private case/evidence authorization."""
        # Create case with image
        create_res = client.post(
            "/api/v1/rescues",
            json={
                "species": "Dog",
                "latitude": 19.0760,
                "longitude": 72.8777,
                "image_url": "evidence/test_nearby.jpg",
            },
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        case_id = create_res.json()["id"]
        case_uuid = uuid.UUID(case_id)

        # Third rescuer views nearby rescues
        nearby_res = client.get(
            "/api/v1/rescues/nearby?lat=19.0760&lng=72.8777&radius_km=10",
            headers={"Authorization": f"Bearer {third_rescuer_token}"},
        )
        assert nearby_res.status_code == 200
        cases = nearby_res.json()
        assert any(c["id"] == case_id for c in cases)

        # Direct private case access is denied (403)
        detail_res = client.get(
            f"/api/v1/rescues/{case_id}",
            headers={"Authorization": f"Bearer {third_rescuer_token}"},
        )
        assert detail_res.status_code == 403

        # Evidence access is denied (403)
        img = db.query(AnimalImage).filter(AnimalImage.rescue_case_id == case_uuid).first()
        if img:
            img_res = client.get(
                f"/api/v1/rescues/{case_id}/images/{img.id}/access",
                headers={"Authorization": f"Bearer {third_rescuer_token}"},
            )
            assert img_res.status_code == 403

    def test_searching_responder_status_alone_does_not_grant_claim_authority(
        self, client, db, citizen_token, third_rescuer_token
    ):
        """11 & 12. SEARCHING_RESPONDER status or UUID knowledge alone does not grant claim authority."""
        create_res = client.post(
            "/api/v1/rescues",
            json={"species": "Cat", "latitude": 19.0760, "longitude": 72.8777},
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        case_id = create_res.json()["id"]
        case_uuid = uuid.UUID(case_id)

        case = db.query(RescueCase).filter(RescueCase.id == case_uuid).first()
        assert case.status == RescueStatus.SEARCHING_RESPONDER

        # Rescuer knows UUID and case is SEARCHING_RESPONDER, but has no offer -> 403
        claim_res = client.post(
            f"/api/v1/rescues/{case_id}/accept",
            headers={"Authorization": f"Bearer {third_rescuer_token}"},
        )
        assert claim_res.status_code == 403
        assert "no active dispatch offer found" in claim_res.text.lower()
