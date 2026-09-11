import pytest
from app.models.user import User
from app.core.security import get_password_hash, create_access_token
from app.core.constants import UserRole

def test_citizen_cannot_set_privileged_status(client, citizen_token):
    # Citizen creates a case
    create_res = client.post(
        "/api/v1/rescues",
        json={"species": "Dog", "latitude": 19.05, "longitude": 72.83},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    case_id = create_res.json()["id"]

    # Citizen tries to set status to RESCUED or UNDER_TREATMENT
    res = client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": "RESCUED"},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    assert res.status_code == 403
    assert "not permitted" in str(res.json())

def test_rescuer_cannot_add_veterinary_treatment(client, citizen_token, rescuer_token, test_facility):
    create_res = client.post(
        "/api/v1/rescues",
        json={"species": "Dog", "latitude": 19.05, "longitude": 72.83},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    case_id = create_res.json()["id"]

    # Rescuer attempts to add treatment
    res = client.post(
        f"/api/v1/rescues/{case_id}/treatments",
        json={
            "diagnosis": "Bone fracture",
            "treatment_notes": "Attempted treatment",
            "facility_id": str(test_facility.id)
        },
        headers={"Authorization": f"Bearer {rescuer_token}"}
    )
    assert res.status_code == 403

def test_veterinarian_cannot_accept_rescuer_mission(client, citizen_token, vet_token):
    create_res = client.post(
        "/api/v1/rescues",
        json={"species": "Dog", "latitude": 19.05, "longitude": 72.83},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    case_id = create_res.json()["id"]

    # Vet tries to accept rescue mission
    res = client.post(
        f"/api/v1/rescues/{case_id}/accept",
        headers={"Authorization": f"Bearer {vet_token}"}
    )
    assert res.status_code == 403

def test_unauthorized_citizen_cannot_view_other_citizen_case(client, db, citizen_token):
    # Create Case 1 reported by Citizen A
    create_res = client.post(
        "/api/v1/rescues",
        json={"species": "Cat", "latitude": 19.05, "longitude": 72.83},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    case_id = create_res.json()["id"]

    # Create Citizen B
    citizen_b = User(
        full_name="Another Citizen",
        email="citizen_b@example.com",
        phone="+919999988888",
        password_hash=get_password_hash("pass"),
        role=UserRole.CITIZEN,
        is_active=True
    )
    db.add(citizen_b)
    db.commit()
    token_b = create_access_token(citizen_b.id)

    # Citizen B tries to fetch Citizen A's case
    res = client.get(
        f"/api/v1/rescues/{case_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res.status_code == 403
