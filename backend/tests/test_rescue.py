import pytest
from app.core.constants import RescueStatus

def test_create_rescue_with_triage(client, citizen_token):
    payload = {
        "species": "Dog",
        "description": "Street dog bleeding after hit-and-run",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "address_text": "Bandra West, Mumbai",
        "bleeding": True,
        "can_walk": False,
        "conscious": True,
        "vehicle_accident": True,
        "breathing_difficulty": True,
        "image_url": "/uploads/test_dog.jpg"
    }
    headers = {"Authorization": f"Bearer {citizen_token}"}
    res = client.post("/api/v1/rescues", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["species"] == "Dog"
    assert data["triage_priority"] == "CRITICAL"
    assert data["triage_score"] >= 80
    assert data["status"] in ["TRIAGED", "SEARCHING_RESPONDER"]
    assert len(data["images"]) == 1
    assert data["images"][0]["image_url"] == "/uploads/test_dog.jpg"

def test_rescue_status_transitions_and_history(client, citizen_token, rescuer_token, vet_token):
    # 1. Citizen creates rescue
    create_res = client.post(
        "/api/v1/rescues",
        json={
            "species": "Cat",
            "latitude": 19.0550,
            "longitude": 72.8400,
            "bleeding": False,
            "can_walk": True
        },
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    case_id = create_res.json()["id"]

    # 2. Rescuer accepts case (TRIAGED -> RESPONDER_ASSIGNED)
    accept_res = client.post(
        f"/api/v1/rescues/{case_id}/accept",
        headers={"Authorization": f"Bearer {rescuer_token}"}
    )
    assert accept_res.status_code == 200

    # 3. Rescuer marks RESPONDER_EN_ROUTE
    patch_res = client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": "RESPONDER_EN_ROUTE", "notes": "Driving to location"},
        headers={"Authorization": f"Bearer {rescuer_token}"}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "RESPONDER_EN_ROUTE"

    # 4. Check timeline history
    timeline_res = client.get(
        f"/api/v1/rescues/{case_id}/timeline",
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    assert timeline_res.status_code == 200
    statuses = [item["new_status"] for item in timeline_res.json()]
    assert "REPORTED" in statuses
    assert "TRIAGED" in statuses
    assert "RESPONDER_ASSIGNED" in statuses
    assert "RESPONDER_EN_ROUTE" in statuses

def test_invalid_status_transition_rejected(client, citizen_token, admin_token):
    # Create case (status = TRIAGED)
    create_res = client.post(
        "/api/v1/rescues",
        json={"species": "Bird", "latitude": 19.05, "longitude": 72.83},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    case_id = create_res.json()["id"]

    # Attempt illegal skip to RESCUED directly from TRIAGED (bypassing assigned, en route, located)
    patch_res = client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": "RESCUED"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert patch_res.status_code == 409
    assert "Invalid status transition" in str(patch_res.json())
