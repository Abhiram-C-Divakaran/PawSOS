import pytest
from app.models.user import User
from app.core.security import get_password_hash, create_access_token
from app.core.constants import UserRole

def test_nearby_rescue_radius_and_distance(client, citizen_token, rescuer_token):
    # Case 1: Close case (~1 km away from 19.0760, 72.8777)
    res1 = client.post(
        "/api/v1/rescues",
        json={"species": "Dog", "latitude": 19.0700, "longitude": 72.8700, "description": "Nearby dog"},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    assert res1.status_code == 200

    # Case 2: Distant case (~50 km away)
    res2 = client.post(
        "/api/v1/rescues",
        json={"species": "Cat", "latitude": 19.5000, "longitude": 73.2000, "description": "Far away cat"},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    assert res2.status_code == 200

    # Query nearby with 10 km radius
    nearby_res = client.get(
        "/api/v1/rescues/nearby?lat=19.0760&lng=72.8777&radius_km=10",
        headers={"Authorization": f"Bearer {rescuer_token}"}
    )
    assert nearby_res.status_code == 200
    cases = nearby_res.json()
    case_species = [c["species"] for c in cases]
    assert "Dog" in case_species
    assert "Cat" not in case_species

    # Confirm real distance_km is returned
    for c in cases:
        if c["species"] == "Dog":
            assert c["distance_km"] is not None
            assert c["distance_km"] > 0
            assert c["distance_km"] <= 10.0

def test_concurrent_acceptance_conflict(client, db, citizen_token, rescuer_token):
    # Rescuer 1 is rescuer_token
    # Create Rescuer 2
    rescuer2 = User(
        full_name="Second Rescuer",
        email="rescuer2@example.com",
        phone="+919700000002",
        password_hash=get_password_hash("pass"),
        role=UserRole.RESCUER,
        is_active=True
    )
    db.add(rescuer2)
    db.commit()
    rescuer2_token = create_access_token(rescuer2.id)

    # Create Case
    create_res = client.post(
        "/api/v1/rescues",
        json={"species": "Dog", "latitude": 19.07, "longitude": 72.87},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    case_id = create_res.json()["id"]

    # Rescuer 1 accepts
    acc1 = client.post(
        f"/api/v1/rescues/{case_id}/accept",
        headers={"Authorization": f"Bearer {rescuer_token}"}
    )
    assert acc1.status_code == 200

    # Rescuer 2 attempts to accept the same case simultaneously
    acc2 = client.post(
        f"/api/v1/rescues/{case_id}/accept",
        headers={"Authorization": f"Bearer {rescuer2_token}"}
    )
    assert acc2.status_code == 409
    assert "already been assigned" in str(acc2.json())
