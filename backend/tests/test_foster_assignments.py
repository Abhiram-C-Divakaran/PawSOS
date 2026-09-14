import uuid
import pytest
from app.models.rescue_case import RescueCase
from app.models.foster_home import FosterHome
from app.models.foster_assignment import FosterAssignment
from app.models.foster_care_update import FosterCareUpdate
from app.models.audit_log import AuditLog
from app.core.constants import RescueStatus, FosterAssignmentStatus, FosterHomeAvailability

def test_foster_assignment_full_lifecycle(client, db, test_org, ngo_admin_token, foster_user, foster_token):
    # Setup Case in RECOVERING
    case = RescueCase(
        case_number="PR-FOST01",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        species="Dog",
        description="Dog needing 2 weeks foster care",
        latitude=19.05,
        longitude=72.83,
        status=RescueStatus.RECOVERING.value,
    )
    db.add(case)

    # Setup Verified Foster Home with capacity 1, occupancy 0
    home = FosterHome(
        caregiver_id=foster_user.id,
        organization_id=test_org.id,
        locality="Bandra",
        latitude=19.05,
        longitude=72.83,
        capacity=1,
        current_occupancy=0,
        verified=True,
        availability_status=FosterHomeAvailability.AVAILABLE.value,
    )
    db.add(home)
    db.commit()

    # 1. NGO creates foster offer
    offer_res = client.post(
        "/api/v1/ngo/foster/assignments",
        json={
            "rescue_case_id": str(case.id),
            "foster_home_id": str(home.id),
            "notes": "Please provide quiet rest area",
        },
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert offer_res.status_code == 200
    assignment_id = offer_res.json()["id"]
    assert offer_res.json()["status"] == "OFFERED"

    # Occupancy must not have changed yet
    db.refresh(home)
    assert home.current_occupancy == 0

    # 2. Caregiver lists assignments and accepts
    list_res = client.get(
        "/api/v1/foster/assignments",
        headers={"Authorization": f"Bearer {foster_token}"},
    )
    assert list_res.status_code == 200
    assert any(a["id"] == assignment_id for a in list_res.json())

    accept_res = client.post(
        f"/api/v1/foster/assignments/{assignment_id}/accept",
        headers={"Authorization": f"Bearer {foster_token}"},
    )
    assert accept_res.status_code == 200
    assert accept_res.json()["status"] == "ACTIVE"

    # Verify home occupancy incremented and availability is now FULL (capacity was 1)
    db.refresh(home)
    assert home.current_occupancy == 1
    assert home.availability_status == FosterHomeAvailability.FULL.value

    # Verify case status advanced to FOSTER_CARE
    db.refresh(case)
    assert case.status == RescueStatus.FOSTER_CARE.value

    # 3. Caregiver submits care update
    update_res = client.post(
        f"/api/v1/foster/assignments/{assignment_id}/care-updates",
        json={
            "general_notes": "Dog is walking with limp but eating well",
            "appetite_status": "NORMAL",
            "activity_status": "NORMAL",
            "weight_kg": 14.5,
            "concern_flag": False,
            "readiness_recommendation": "READY_FOR_ADOPTION",
        },
        headers={"Authorization": f"Bearer {foster_token}"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["readiness_recommendation"] == "READY_FOR_ADOPTION"

    # Read care updates
    get_updates = client.get(
        f"/api/v1/foster/assignments/{assignment_id}/care-updates",
        headers={"Authorization": f"Bearer {foster_token}"},
    )
    assert get_updates.status_code == 200
    assert len(get_updates.json()) == 1

    # 4. NGO completes foster assignment
    comp_res = client.post(
        f"/api/v1/ngo/foster/assignments/{assignment_id}/complete",
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "COMPLETED"

    # Occupancy decremented back to 0 and home is AVAILABLE again
    db.refresh(home)
    assert home.current_occupancy == 0
    assert home.availability_status == FosterHomeAvailability.AVAILABLE.value

    # 5. Idempotent test: repeated complete call does not decrement occupancy below 0
    comp_repeat = client.post(
        f"/api/v1/ngo/foster/assignments/{assignment_id}/complete",
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert comp_repeat.status_code == 200
    db.refresh(home)
    assert home.current_occupancy == 0


def test_foster_offer_decline(client, db, test_org, ngo_admin_token, foster_user, foster_token):
    case = RescueCase(
        case_number="PR-FOST02",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        species="Cat",
        latitude=19.05,
        longitude=72.83,
        status=RescueStatus.RECOVERING.value,
    )
    home = FosterHome(
        caregiver_id=foster_user.id,
        organization_id=test_org.id,
        locality="Bandra",
        latitude=19.05,
        longitude=72.83,
        capacity=2,
        current_occupancy=0,
        verified=True,
    )
    db.add_all([case, home])
    db.commit()

    # Create offer
    offer_res = client.post(
        "/api/v1/ngo/foster/assignments",
        json={"rescue_case_id": str(case.id), "foster_home_id": str(home.id)},
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assignment_id = offer_res.json()["id"]

    # Decline offer
    decline_res = client.post(
        f"/api/v1/foster/assignments/{assignment_id}/decline",
        headers={"Authorization": f"Bearer {foster_token}"},
    )
    assert decline_res.status_code == 200
    assert decline_res.json()["status"] == "DECLINED"

    db.refresh(home)
    assert home.current_occupancy == 0
