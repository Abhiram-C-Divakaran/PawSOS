import uuid
import pytest
from app.models.rescue_case import RescueCase
from app.models.foster_home import FosterHome
from app.models.foster_assignment import FosterAssignment
from app.core.constants import RescueStatus, FosterAssignmentStatus, FosterHomeAvailability

def test_foster_capacity_overbooking_protection(client, db, test_org, foster_user, foster_token):
    # Foster home with capacity = 1
    home = FosterHome(
        caregiver_id=foster_user.id,
        organization_id=test_org.id,
        locality="Juhu",
        latitude=19.10,
        longitude=72.82,
        capacity=1,
        current_occupancy=0,
        verified=True,
        availability_status=FosterHomeAvailability.AVAILABLE.value,
    )
    db.add(home)

    # Case 1 & Case 2
    case1 = RescueCase(
        case_number="PR-RACE01",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        species="Dog",
        latitude=19.10,
        longitude=72.82,
        status=RescueStatus.RECOVERING.value,
    )
    case2 = RescueCase(
        case_number="PR-RACE02",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        species="Dog",
        latitude=19.10,
        longitude=72.82,
        status=RescueStatus.RECOVERING.value,
    )
    db.add_all([case1, case2])
    db.commit()

    # Assign two offers to the same home
    assign1 = FosterAssignment(
        animal_id=uuid.uuid4(),
        rescue_case_id=case1.id,
        foster_home_id=home.id,
        status=FosterAssignmentStatus.OFFERED.value,
    )
    assign2 = FosterAssignment(
        animal_id=uuid.uuid4(),
        rescue_case_id=case2.id,
        foster_home_id=home.id,
        status=FosterAssignmentStatus.OFFERED.value,
    )
    db.add_all([assign1, assign2])
    db.commit()

    # Accept first offer -> Succeeds
    res1 = client.post(
        f"/api/v1/foster/assignments/{assign1.id}/accept",
        headers={"Authorization": f"Bearer {foster_token}"},
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "ACTIVE"

    db.refresh(home)
    assert home.current_occupancy == 1
    assert home.availability_status == FosterHomeAvailability.FULL.value

    # Accept second offer -> Fails with 409 Conflict due to capacity check
    res2 = client.post(
        f"/api/v1/foster/assignments/{assign2.id}/accept",
        headers={"Authorization": f"Bearer {foster_token}"},
    )
    assert res2.status_code == 409
    assert "capacity" in res2.json()["detail"].lower()

    # Verify home occupancy was NOT overbooked
    db.refresh(home)
    assert home.current_occupancy == 1
