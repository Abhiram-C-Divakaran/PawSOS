import uuid
import pytest
from app.models.rescue_case import RescueCase
from app.models.animal import Animal
from app.core.constants import RescueStatus

def test_adoption_listing_eligibility_and_lifecycle(client, db, test_org, ngo_admin_token):
    # Setup animal
    animal = Animal(
        species="Dog",
        sex="Female",
        approx_age="2 years",
        colour="Golden",
        description="Gentle and loving dog",
        identifying_marks="White chest patch",
        sterilization_status="Spayed",
        vaccination_status="Fully Vaccinated",
    )
    db.add(animal)
    db.commit()

    # Case 1: Still in RECOVERING -> Listing creation must be rejected
    case_recovering = RescueCase(
        case_number="PR-ELIG01",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        animal_id=animal.id,
        species="Dog",
        latitude=19.05,
        longitude=72.83,
        status=RescueStatus.RECOVERING.value,
    )
    db.add(case_recovering)
    db.commit()

    res_ineligible = client.post(
        "/api/v1/ngo/adoptions/listings",
        json={
            "rescue_case_id": str(case_recovering.id),
            "title": "Luna - Sweet Golden Retriever",
            "public_description": "Friendly family dog looking for a forever home",
        },
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert res_ineligible.status_code == 400
    assert "READY_FOR_ADOPTION" in res_ineligible.json()["detail"]

    # Case 2: In READY_FOR_ADOPTION -> Listing creation succeeds as DRAFT
    case_ready = RescueCase(
        case_number="PR-ELIG02",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        animal_id=animal.id,
        species="Dog",
        latitude=19.05,
        longitude=72.83,
        status=RescueStatus.READY_FOR_ADOPTION.value,
    )
    db.add(case_ready)
    db.commit()

    res_create = client.post(
        "/api/v1/ngo/adoptions/listings",
        json={
            "rescue_case_id": str(case_ready.id),
            "title": "Luna - Sweet Golden Dog",
            "public_description": "Friendly family companion looking for a forever home",
            "public_image_url": "https://cdn.pawreach.org/public/luna.jpg",
        },
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert res_create.status_code == 200
    listing_id = res_create.json()["id"]
    assert res_create.json()["status"] == "DRAFT"

    # Public browse must NOT show DRAFT listing
    public_browse1 = client.get("/api/v1/adoptions")
    assert public_browse1.status_code == 200
    assert not any(l["id"] == listing_id for l in public_browse1.json())

    # NGO publishes listing
    publish_res = client.post(
        f"/api/v1/ngo/adoptions/listings/{listing_id}/publish",
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert publish_res.status_code == 200
    assert publish_res.json()["status"] == "PUBLISHED"
    assert publish_res.json()["published_at"] is not None

    # Public browse now shows PUBLISHED listing
    public_browse2 = client.get("/api/v1/adoptions")
    assert public_browse2.status_code == 200
    published_item = next((l for l in public_browse2.json() if l["id"] == listing_id), None)
    assert published_item is not None
    assert published_item["title"] == "Luna - Sweet Golden Dog"
    assert published_item["species"] == "Dog"
    assert published_item["sterilization_status"] == "Spayed"
    assert published_item["organization_name"] == test_org.name

    # NGO pauses listing
    pause_res = client.post(
        f"/api/v1/ngo/adoptions/listings/{listing_id}/pause",
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "PAUSED"

    # Public browse no longer returns PAUSED listing
    public_browse3 = client.get("/api/v1/adoptions")
    assert not any(l["id"] == listing_id for l in public_browse3.json())
