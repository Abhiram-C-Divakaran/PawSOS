import uuid
from datetime import datetime, timedelta
import pytest
from app.models.rescue_case import RescueCase
from app.models.animal import Animal
from app.models.adoption_listing import AdoptionListing
from app.models.adoption_application import AdoptionApplication
from app.models.organization import Organization
from app.models.user import User
from app.core.constants import RescueStatus, AdoptionListingStatus, UserRole, OrganizationType
from app.core.security import get_password_hash, create_access_token

def test_ngo_adoption_review_and_visit_scheduling(client, db, test_org, ngo_admin_token, citizen_user):
    animal = Animal(species="Dog", sex="Male", description="Playful puppy")
    db.add(animal)
    db.commit()

    case = RescueCase(
        case_number="PR-REV01",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        animal_id=animal.id,
        species="Dog",
        latitude=19.05,
        longitude=72.83,
        status=RescueStatus.READY_FOR_ADOPTION.value,
    )
    db.add(case)
    db.commit()

    listing = AdoptionListing(
        animal_id=animal.id,
        rescue_case_id=case.id,
        organization_id=test_org.id,
        title="Max - Energetic Puppy",
        public_description="Looking for an active companion",
        status=AdoptionListingStatus.PUBLISHED.value,
        created_by=citizen_user.id,
    )
    db.add(listing)
    db.commit()

    application = AdoptionApplication(
        listing_id=listing.id,
        applicant_id=citizen_user.id,
        reason_for_adoption="Great fenced yard and experience with dogs",
    )
    db.add(application)
    db.commit()

    # 1. NGO lists applications for this listing
    apps_res = client.get(
        f"/api/v1/ngo/adoptions/listings/{listing.id}/applications",
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert apps_res.status_code == 200
    assert len(apps_res.json()) == 1
    assert apps_res.json()[0]["id"] == str(application.id)
    assert apps_res.json()[0]["applicant_name"] == citizen_user.full_name

    # 2. NGO moves application to UNDER_REVIEW
    review_res = client.post(
        f"/api/v1/ngo/adoptions/applications/{application.id}/review",
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == "UNDER_REVIEW"

    # 3. NGO schedules adoption visit
    visit_time = (datetime.utcnow() + timedelta(days=2)).isoformat()
    visit_res = client.post(
        f"/api/v1/ngo/adoptions/applications/{application.id}/visits",
        json={"scheduled_at": visit_time, "notes": "Meet and greet at shelter facility"},
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert visit_res.status_code == 200
    visit_id = visit_res.json()["id"]
    assert visit_res.json()["status"] == "SCHEDULED"

    # 4. NGO updates visit to COMPLETED
    visit_patch = client.patch(
        f"/api/v1/ngo/adoptions/visits/{visit_id}",
        json={"status": "COMPLETED", "notes": "Great interaction with animal"},
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert visit_patch.status_code == 200
    assert visit_patch.json()["status"] == "COMPLETED"


def test_cross_tenant_ngo_review_denied(client, db, test_org, citizen_user):
    # Org B
    org_b = Organization(
        name="Other NGO",
        organization_type=OrganizationType.NGO,
        email="other_ngo@example.com",
        phone="+912226008888",
        verification_status=True,
    )
    db.add(org_b)
    db.commit()

    other_admin = User(
        full_name="Other NGO Admin",
        email="other_admin@example.com",
        phone="+919988776655",
        password_hash=get_password_hash("pass"),
        role=UserRole.NGO_ADMIN,
        organization_id=org_b.id,
        is_active=True,
    )
    db.add(other_admin)
    db.commit()
    other_token = create_access_token(other_admin.id)

    # Listing belongs to test_org (Org A)
    case = RescueCase(
        case_number="PR-TEN01",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        species="Dog",
        latitude=19.05,
        longitude=72.83,
        status=RescueStatus.READY_FOR_ADOPTION.value,
    )
    db.add(case)
    db.commit()

    listing = AdoptionListing(
        animal_id=uuid.uuid4(),
        rescue_case_id=case.id,
        organization_id=test_org.id,
        title="Charlie",
        public_description="Friendly dog",
        status=AdoptionListingStatus.PUBLISHED.value,
        created_by=citizen_user.id,
    )
    db.add(listing)
    db.commit()

    app = AdoptionApplication(
        listing_id=listing.id,
        applicant_id=citizen_user.id,
        reason_for_adoption="Looking for a pet",
    )
    db.add(app)
    db.commit()

    # Other NGO admin attempts to review -> 403 Forbidden
    res = client.get(
        f"/api/v1/ngo/adoptions/listings/{listing.id}/applications",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert res.status_code == 403
