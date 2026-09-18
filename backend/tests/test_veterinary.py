import pytest

def test_veterinary_inbox_and_treatment_flow(client, citizen_token, rescuer_token, vet_token, test_facility):
    # 1. Citizen creates rescue
    create_res = client.post(
        "/api/v1/rescues",
        json={"species": "Dog", "latitude": 19.0760, "longitude": 72.8777},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    case_id = create_res.json()["id"]

    # 2. Rescuer accepts and transports to facility
    acc_res = client.post(f"/api/v1/rescues/{case_id}/accept", headers={"Authorization": f"Bearer {rescuer_token}"})
    assert acc_res.status_code == 200
    client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": "RESPONDER_EN_ROUTE"},
        headers={"Authorization": f"Bearer {rescuer_token}"}
    )
    client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": "ANIMAL_LOCATED"},
        headers={"Authorization": f"Bearer {rescuer_token}"}
    )
    client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": "RESCUED"},
        headers={"Authorization": f"Bearer {rescuer_token}"}
    )
    client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": "TRANSPORTING", "veterinary_facility_id": str(test_facility.id)},
        headers={"Authorization": f"Bearer {rescuer_token}"}
    )
    client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": "AT_VETERINARY_FACILITY"},
        headers={"Authorization": f"Bearer {rescuer_token}"}
    )

    # 3. Vet checks inbox
    vet_inbox = client.get("/api/v1/veterinary/cases", headers={"Authorization": f"Bearer {vet_token}"})
    assert vet_inbox.status_code == 200
    case_ids = [c["id"] for c in vet_inbox.json()]
    assert case_id in case_ids

    # 4. Vet records treatment
    treatment_res = client.post(
        f"/api/v1/rescues/{case_id}/treatments",
        json={
            "diagnosis": "Right hindleg tibia fracture",
            "treatment_notes": "Splint applied, analgesic administered",
            "medications": "Meloxicam 0.2mg/kg",
            "facility_id": str(test_facility.id)
        },
        headers={"Authorization": f"Bearer {vet_token}"}
    )
    assert treatment_res.status_code == 200
    assert treatment_res.json()["diagnosis"] == "Right hindleg tibia fracture"

    # 5. Verify case is now UNDER_TREATMENT
    case_check = client.get(f"/api/v1/rescues/{case_id}", headers={"Authorization": f"Bearer {vet_token}"})
    assert case_check.json()["status"] == "UNDER_TREATMENT"

    # 6. Vet progresses case to RECOVERING then READY_FOR_RELEASE then CLOSED
    rec_res = client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": "RECOVERING"},
        headers={"Authorization": f"Bearer {vet_token}"}
    )
    assert rec_res.status_code == 200
    assert rec_res.json()["status"] == "RECOVERING"

    rel_res = client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": "READY_FOR_RELEASE"},
        headers={"Authorization": f"Bearer {vet_token}"}
    )
    assert rel_res.status_code == 200

    close_res = client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": "RELEASED"},
        headers={"Authorization": f"Bearer {vet_token}"}
    )
    assert close_res.status_code == 200

    final_close = client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": "CLOSED"},
        headers={"Authorization": f"Bearer {vet_token}"}
    )
    assert final_close.status_code == 200
    assert final_close.json()["status"] == "CLOSED"
    assert final_close.json()["closed_at"] is not None
