import uuid
import pytest
from app.models.user import User
from app.models.rescue_case import RescueCase
from app.models.foster_home import FosterHome
from app.core.constants import UserRole, RescueStatus, RescuePriority
from app.core.security import get_password_hash, create_access_token

def test_deterministic_foster_matching(client, db, test_org, ngo_admin_token):
    # 1. Create a rescue case in RECOVERING
    case = RescueCase(
        case_number="PR-MATCH01",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        species="Dog",
        description="Dog recovering from fracture",
        latitude=19.05,
        longitude=72.83,
        status=RescueStatus.RECOVERING.value,
        triage_priority=RescuePriority.CRITICAL,  # requires medical support
    )
    db.add(case)

    # Helper to create caregivers & homes
    def create_home(name, species, medical, cap, occ, ver, avail="AVAILABLE", org_id=test_org.id):
        user = User(
            full_name=name,
            email=f"{name.lower().replace(' ', '')}@example.com",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
            password_hash=get_password_hash("pass"),
            role=UserRole.FOSTER,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        h = FosterHome(
            caregiver_id=user.id,
            organization_id=org_id,
            locality="Test Locality",
            latitude=19.05,
            longitude=72.83,
            accepted_species=species,
            medical_care_supported=medical,
            capacity=cap,
            current_occupancy=occ,
            verified=ver,
            availability_status=avail,
        )
        db.add(h)
        db.commit()
        db.refresh(h)
        return h

    # Candidate 1: Perfect match (Dog, Medical: True, Verified: True, Avail: AVAILABLE, Remaining: 2)
    h1 = create_home("Caregiver Perfect", "Dog, Cat", True, 3, 1, True)

    # Candidate 2: Species match but lacks medical care (Dog, Medical: False, Verified: True)
    h2 = create_home("Caregiver Basic", "Dog", False, 2, 0, True)

    # Candidate 3: Unverified home (should be excluded)
    h3 = create_home("Caregiver Unverified", "Dog", True, 2, 0, False)

    # Candidate 4: At full capacity (should be excluded)
    h4 = create_home("Caregiver Full", "Dog", True, 2, 2, True)

    # Candidate 5: Paused availability (should be excluded)
    h5 = create_home("Caregiver Paused", "Dog", True, 2, 0, True, avail="PAUSED")

    # Candidate 6: Different species preference (Cat only)
    h6 = create_home("Caregiver CatOnly", "Cat", True, 2, 0, True)

    # Request matches
    res = client.post(
        "/api/v1/ngo/foster/matches",
        json={"case_id": str(case.id)},
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()

    # Assert excluded candidates are not in candidates list
    candidate_ids = [c["foster_home_id"] for c in data]
    assert str(h3.id) not in candidate_ids  # unverified
    assert str(h4.id) not in candidate_ids  # full
    assert str(h5.id) not in candidate_ids  # paused

    # Assert candidate 1 is top ranked
    assert str(h1.id) == data[0]["foster_home_id"]
    assert data[0]["compatible"] is True
    assert data[0]["species_match"] is True
    assert data[0]["medical_support_match"] is True
    assert data[0]["match_score"] > 80.0

    # Assert Candidate 2 is marked incompatible due to medical requirement
    c2 = next(c for c in data if c["foster_home_id"] == str(h2.id))
    assert c2["medical_support_match"] is False
    assert c2["compatible"] is False
