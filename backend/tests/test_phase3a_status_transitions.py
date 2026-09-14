import uuid
import pytest
from app.models.rescue_case import RescueCase
from app.models.animal import Animal
from app.models.adoption_listing import AdoptionListing
from app.core.constants import RescueStatus, AdoptionListingStatus

def test_full_foster_and_adoption_status_transitions(client, db, test_org, ngo_admin_token, vet_token, foster_token):
    # Setup animal & case in RECOVERING
    animal = Animal(species="Dog", description="Post-surgery recovery")
    db.add(animal)
    db.commit()

    case = RescueCase(
        case_number="PR-TRANS01",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        animal_id=animal.id,
        species="Dog",
        latitude=19.05,
        longitude=72.83,
        status=RescueStatus.RECOVERING.value,
    )
    db.add(case)
    db.commit()

    # 1. FOSTER caregiver attempts to directly set READY_FOR_ADOPTION -> 403 Forbidden
    foster_fail = client.patch(
        f"/api/v1/rescues/{case.id}/status",
        json={"status": RescueStatus.READY_FOR_ADOPTION.value},
        headers={"Authorization": f"Bearer {foster_token}"},
    )
    assert foster_fail.status_code == 403

    # 2. Advance RECOVERING -> FOSTER_CARE (via NGO / Vet)
    res_foster = client.patch(
        f"/api/v1/rescues/{case.id}/status",
        json={"status": RescueStatus.FOSTER_CARE.value, "notes": "Placed in foster care"},
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert res_foster.status_code == 200
    assert res_foster.json()["status"] == RescueStatus.FOSTER_CARE.value

    # 3. Advance FOSTER_CARE -> READY_FOR_ADOPTION (via Veterinarian or NGO Admin)
    res_ready = client.patch(
        f"/api/v1/rescues/{case.id}/status",
        json={"status": RescueStatus.READY_FOR_ADOPTION.value, "notes": "Fully healed and ready for adoption"},
        headers={"Authorization": f"Bearer {vet_token}"},
    )
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == RescueStatus.READY_FOR_ADOPTION.value

    # 4. Advance READY_FOR_ADOPTION -> ADOPTED
    res_adopt = client.patch(
        f"/api/v1/rescues/{case.id}/status",
        json={"status": RescueStatus.ADOPTED.value, "notes": "Adoption contract signed"},
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert res_adopt.status_code == 200
    assert res_adopt.json()["status"] == RescueStatus.ADOPTED.value

    # 5. Advance ADOPTED -> CLOSED
    res_close = client.patch(
        f"/api/v1/rescues/{case.id}/status",
        json={"status": RescueStatus.CLOSED.value, "notes": "Post-adoption check completed"},
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert res_close.status_code == 200
    assert res_close.json()["status"] == RescueStatus.CLOSED.value


def test_release_workflow_and_adoption_listing_closure(client, db, test_org, ngo_admin_token, vet_token):
    case = RescueCase(
        case_number="PR-REL01",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        species="Monkey",
        latitude=19.05,
        longitude=72.83,
        status=RescueStatus.RECOVERING.value,
    )
    db.add(case)
    db.commit()

    # Move to FOSTER_CARE
    client.patch(
        f"/api/v1/rescues/{case.id}/status",
        json={"status": RescueStatus.FOSTER_CARE.value},
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )

    # Inadvertent draft listing
    listing = AdoptionListing(
        animal_id=uuid.uuid4(),
        rescue_case_id=case.id,
        organization_id=test_org.id,
        title="Wildlife Monkey",
        public_description="Native wildlife in care",
        status=AdoptionListingStatus.DRAFT.value,
        created_by=uuid.uuid4(),
    )
    db.add(listing)
    db.commit()

    # Case judged suitable for release: FOSTER_CARE -> READY_FOR_RELEASE
    res_rel_ready = client.patch(
        f"/api/v1/rescues/{case.id}/status",
        json={"status": RescueStatus.READY_FOR_RELEASE.value, "notes": "Animal rehabilitated for release to wild"},
        headers={"Authorization": f"Bearer {vet_token}"},
    )
    assert res_rel_ready.status_code == 200
    assert res_rel_ready.json()["status"] == RescueStatus.READY_FOR_RELEASE.value

    # Listing must have been automatically closed
    db.refresh(listing)
    assert listing.status == AdoptionListingStatus.CLOSED.value

    # READY_FOR_RELEASE -> RELEASED
    res_released = client.patch(
        f"/api/v1/rescues/{case.id}/status",
        json={"status": RescueStatus.RELEASED.value, "notes": "Successfully released into Sanjay Gandhi National Park"},
        headers={"Authorization": f"Bearer {vet_token}"},
    )
    assert res_released.status_code == 200
    assert res_released.json()["status"] == RescueStatus.RELEASED.value

    # RELEASED -> CLOSED
    res_closed = client.patch(
        f"/api/v1/rescues/{case.id}/status",
        json={"status": RescueStatus.CLOSED.value, "notes": "Case concluded"},
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert res_closed.status_code == 200
    assert res_closed.json()["status"] == RescueStatus.CLOSED.value
