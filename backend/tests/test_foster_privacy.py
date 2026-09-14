import uuid
import pytest
from app.models.rescue_case import RescueCase
from app.models.foster_home import FosterHome
from app.core.constants import RescueStatus

def test_foster_location_and_pii_privacy(client, db, test_org, ngo_admin_token, foster_user, foster_token, citizen_token):
    home = FosterHome(
        caregiver_id=foster_user.id,
        organization_id=test_org.id,
        locality="Khar Danda",
        latitude=19.0699,
        longitude=72.8299,
        capacity=2,
        current_occupancy=0,
        verified=True,
    )
    db.add(home)
    db.commit()

    # 1. Matching candidate response only returns safe coarse locality and NO exact lat/lon
    case = RescueCase(
        case_number="PR-PRIV01",
        reporter_id=uuid.uuid4(),
        organization_id=test_org.id,
        species="Dog",
        latitude=19.05,
        longitude=72.83,
        status=RescueStatus.RECOVERING.value,
    )
    db.add(case)
    db.commit()

    match_res = client.post(
        "/api/v1/ngo/foster/matches",
        json={"case_id": str(case.id)},
        headers={"Authorization": f"Bearer {ngo_admin_token}"},
    )
    assert match_res.status_code == 200
    candidate = next(c for c in match_res.json() if c["foster_home_id"] == str(home.id))
    assert "latitude" not in candidate
    assert "longitude" not in candidate
    assert candidate["locality"] == "Khar Danda"

    # 2. Citizen cannot access NGO foster management endpoints
    citizen_ngo_res = client.get(
        "/api/v1/ngo/foster/homes",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert citizen_ngo_res.status_code == 403

    # 3. Citizen cannot access foster's private profile
    citizen_foster_res = client.get(
        f"/api/v1/ngo/foster/homes/{home.id}",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert citizen_foster_res.status_code == 403
