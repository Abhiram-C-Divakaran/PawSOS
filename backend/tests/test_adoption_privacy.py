import uuid
import pytest
from app.models.rescue_case import RescueCase
from app.models.animal import Animal
from app.models.adoption_listing import AdoptionListing
from app.models.adoption_application import AdoptionApplication
from app.models.foster_home import FosterHome
from app.models.user import User
from app.core.constants import RescueStatus, AdoptionListingStatus, UserRole
from app.core.security import get_password_hash

def test_public_adoption_privacy_guarantees(client, db, test_org, foster_user):
    # Reporter
    reporter = User(
        full_name="Secret Citizen",
        email="secret@example.com",
        phone="+919811223344",
        password_hash=get_password_hash("pass"),
        role=UserRole.CITIZEN,
        is_active=True,
    )
    db.add(reporter)
    db.commit()

    animal = Animal(
        species="Dog",
        sex="Male",
        approx_age="1 year",
        colour="Brown",
        description="Friendly and vaccinated",
        identifying_marks="Curled tail",
        sterilization_status="Neutered",
        vaccination_status="Complete",
    )
    db.add(animal)
    db.commit()

    # Case with sensitive private rescue coordinates and reporter
    case = RescueCase(
        case_number="PR-PRIV99",
        reporter_id=reporter.id,
        organization_id=test_org.id,
        animal_id=animal.id,
        species="Dog",
        latitude=18.9220,  # Exact Gateway of India coordinates
        longitude=72.8347,
        address_text="Private Residence Area, Gate 4",
        status=RescueStatus.READY_FOR_ADOPTION.value,
    )
    db.add(case)
    db.commit()

    # Foster home with private location
    home = FosterHome(
        caregiver_id=foster_user.id,
        organization_id=test_org.id,
        locality="Colaba Safe Zone",
        latitude=18.9100,
        longitude=72.8200,
        capacity=2,
        current_occupancy=1,
        verified=True,
    )
    db.add(home)

    listing = AdoptionListing(
        animal_id=animal.id,
        rescue_case_id=case.id,
        organization_id=test_org.id,
        title="Brownie - Charming Young Dog",
        public_description="Playful and loving dog looking for a forever home",
        public_image_url="https://cdn.pawreach.org/public/brownie.jpg",
        status=AdoptionListingStatus.PUBLISHED.value,
        created_by=foster_user.id,
    )
    db.add(listing)
    db.commit()

    # Query public catalog
    res = client.get("/api/v1/adoptions")
    assert res.status_code == 200
    item = next(l for l in res.json() if l["id"] == str(listing.id))

    # Assert NO private case or reporter details are leaked
    assert "reporter_id" not in item
    assert "reporter_phone" not in item
    assert "reporter_email" not in item
    assert "latitude" not in item
    assert "longitude" not in item
    assert "address_text" not in item
    assert "caregiver_id" not in item
    assert "caregiver_phone" not in item

    # Query single detail
    res_detail = client.get(f"/api/v1/adoptions/{listing.id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert "latitude" not in detail
    assert "longitude" not in detail
    assert "reporter_id" not in detail
    assert detail["title"] == "Brownie - Charming Young Dog"
    assert detail["species"] == "Dog"
    assert detail["sterilization_status"] == "Neutered"
