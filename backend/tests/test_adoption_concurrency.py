import uuid
import pytest
from app.models.rescue_case import RescueCase
from app.models.animal import Animal
from app.models.adoption_listing import AdoptionListing
from app.models.adoption_application import AdoptionApplication
from app.models.foster_home import FosterHome
from app.models.foster_assignment import FosterAssignment
from app.models.user import User
from app.core.constants import (
    RescueStatus,
    AdoptionListingStatus,
    AdoptionApplicationStatus,
    FosterAssignmentStatus,
    FosterHomeAvailability,
    UserRole,
)
from app.core.security import get_password_hash

def test_transactional_adoption_approval_and_concurrency(client, db, test_org, ngo_admin_token, foster_user):
    animal = Animal(species="Dog", sex="Female", description="Gentle rescue dog")
    db.add(animal)
    db.commit()

    case = RescueCase(
        case_number="PR-APPR01",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        animal_id=animal.id,
        species="Dog",
        latitude=19.05,
        longitude=72.83,
        status=RescueStatus.READY_FOR_ADOPTION.value,
    )
    db.add(case)

    # Active foster home & assignment
    home = FosterHome(
        caregiver_id=foster_user.id,
        organization_id=test_org.id,
        locality="Juhu",
        latitude=19.10,
        longitude=72.82,
        capacity=1,
        current_occupancy=1,
        verified=True,
        availability_status=FosterHomeAvailability.FULL.value,
    )
    db.add(home)
    db.commit()

    foster_assign = FosterAssignment(
        animal_id=animal.id,
        rescue_case_id=case.id,
        foster_home_id=home.id,
        status=FosterAssignmentStatus.ACTIVE.value,
    )
    db.add(foster_assign)

    listing = AdoptionListing(
        animal_id=animal.id,
        rescue_case_id=case.id,
        organization_id=test_org.id,
        title="Bella - Loving Companion",
        public_description="Looking for a warm home",
        status=AdoptionListingStatus.PUBLISHED.value,
        created_by=foster_user.id,
    )
    db.add(listing)

    # Create Applicant 1 & Applicant 2
    user1 = User(
        full_name="Applicant One",
        email="applicant1@example.com",
        phone="+919800000001",
        password_hash=get_password_hash("pass"),
        role=UserRole.CITIZEN,
        is_active=True,
    )
    user2 = User(
        full_name="Applicant Two",
        email="applicant2@example.com",
        phone="+919800000002",
        password_hash=get_password_hash("pass"),
        role=UserRole.CITIZEN,
        is_active=True,
    )
    db.add_all([user1, user2])
    db.commit()

    app1 = AdoptionApplication(
        listing_id=listing.id,
        applicant_id=user1.id,
        reason_for_adoption="Experienced dog owner with huge garden",
        status=AdoptionApplicationStatus.UNDER_REVIEW.value,
    )
    app2 = AdoptionApplication(
        listing_id=listing.id,
        applicant_id=user2.id,
        reason_for_adoption="Loving family wanting a pet",
        status=AdoptionApplicationStatus.UNDER_REVIEW.value,
    )
    db.add_all([app1, app2])
    db.commit()

    # 1. Approve Applicant 1
    approve_res1 = client.post(
        f"/api/v1/ngo/adoptions/applications/{app1.id}/approve",
        json={"decision_notes": "Perfect match after home inspection"},
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert approve_res1.status_code == 200
    assert approve_res1.json()["status"] == "APPROVED"

    # Verify listing is CLOSED
    db.refresh(listing)
    assert listing.status == AdoptionListingStatus.CLOSED.value
    assert listing.closed_at is not None

    # Verify case status transitioned to ADOPTED
    db.refresh(case)
    assert case.status == RescueStatus.ADOPTED.value

    # Verify active foster assignment was automatically COMPLETED and occupancy decremented
    db.refresh(foster_assign)
    assert foster_assign.status == FosterAssignmentStatus.COMPLETED.value
    db.refresh(home)
    assert home.current_occupancy == 0
    assert home.availability_status == FosterHomeAvailability.AVAILABLE.value

    # Verify other pending application (app2) was automatically marked REJECTED
    db.refresh(app2)
    assert app2.status == AdoptionApplicationStatus.REJECTED.value
    assert "Another applicant was approved" in (app2.decision_notes or "")

    # 2. Concurrency test: Attempting to approve Application 2 now fails with 409 Conflict
    approve_res2 = client.post(
        f"/api/v1/ngo/adoptions/applications/{app2.id}/approve",
        json={"decision_notes": "Attempting second approval"},
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert approve_res2.status_code == 409
    assert "Another applicant was approved" in approve_res2.json()["detail"] or "no longer published" in approve_res2.json()["detail"]
