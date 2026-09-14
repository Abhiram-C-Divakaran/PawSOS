import uuid
import pytest
from app.models.rescue_case import RescueCase
from app.models.animal import Animal
from app.models.adoption_listing import AdoptionListing
from app.models.user import User
from app.core.constants import RescueStatus, AdoptionListingStatus, UserRole
from app.core.security import get_password_hash, create_access_token

def test_adoption_application_submission_and_tracking(client, db, test_org, citizen_user, citizen_token):
    animal = Animal(species="Cat", sex="Male", description="Friendly ginger cat")
    db.add(animal)
    db.commit()

    case = RescueCase(
        case_number="PR-APPL01",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        animal_id=animal.id,
        species="Cat",
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
        title="Oliver - Gentle Tabby",
        public_description="Loves sunbeams and purring loudly",
        status=AdoptionListingStatus.PUBLISHED.value,
        created_by=citizen_user.id,
    )
    db.add(listing)
    db.commit()

    # 1. Citizen applies
    app_payload = {
        "housing_type": "APARTMENT",
        "owns_or_rents": "OWNS",
        "household_size": 2,
        "existing_pets": "None",
        "reason_for_adoption": "Looking to provide a loving and safe indoor home for Oliver.",
        "care_plan": "Regular vet visits and premium nutrition",
    }
    apply_res = client.post(
        f"/api/v1/adoptions/{listing.id}/apply",
        json=app_payload,
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert apply_res.status_code == 200
    app_id = apply_res.json()["id"]
    assert apply_res.json()["status"] == "SUBMITTED"
    assert apply_res.json()["listing_title"] == "Oliver - Gentle Tabby"

    # 2. Duplicate active application attempt rejected with 409
    dup_res = client.post(
        f"/api/v1/adoptions/{listing.id}/apply",
        json=app_payload,
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert dup_res.status_code == 409
    assert "already submitted an active application" in dup_res.json()["detail"]

    # 3. Citizen lists own applications
    my_apps = client.get(
        "/api/v1/adoption-applications",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert my_apps.status_code == 200
    assert len(my_apps.json()) == 1
    assert my_apps.json()[0]["id"] == app_id

    # 4. Another citizen attempts to view application -> 403 Forbidden
    other_citizen = User(
        full_name="Other Person",
        email="other@example.com",
        phone="+919870001111",
        password_hash=get_password_hash("pass"),
        role=UserRole.CITIZEN,
        is_active=True,
    )
    db.add(other_citizen)
    db.commit()
    other_token = create_access_token(other_citizen.id)

    unauth_res = client.get(
        f"/api/v1/adoption-applications/{app_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert unauth_res.status_code == 403

    # 5. Citizen withdraws application
    withdraw_res = client.post(
        f"/api/v1/adoption-applications/{app_id}/withdraw",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert withdraw_res.status_code == 200
    assert withdraw_res.json()["status"] == "WITHDRAWN"
