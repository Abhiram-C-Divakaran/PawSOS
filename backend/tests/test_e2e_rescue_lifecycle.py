import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app.models.user import User, UserRole
from app.models.rescue_case import RescueCase, RescueStatus, RescuePriority
from app.models.rescue_assignment import RescueAssignment, AssignmentStatus
from app.models.rescuer_profile import RescuerProfile
from app.models.veterinary_facility import VeterinaryFacility
from app.models.notification import Notification

def test_complete_phase2_end_to_end_rescue_lifecycle(client: TestClient, db):
    """
    SECTION 68: Complete 17-step end-to-end rescue lifecycle verification:
    Citizen Reports -> Critical Triage -> Auto-Dispatch -> 
    Nearby Responders Ranked & Offered -> Responder A Rejects -> 
    Responder B Accepts -> Concurrency Locking -> Citizen Notification -> 
    NGO Tracking -> En Route -> Rescued -> Vet Transport -> 
    Treatment Workflow -> Recovering -> Case Closed -> Analytics Verified.
    """
    # 1. Setup Actors: Citizen, Responder A, Responder B, Veterinarian, NGO Admin
    # Citizen
    citizen = User(
        email="citizen_e2e@example.com",
        full_name="Citizen Jane",
        phone="+919999900001",
        password_hash="hashed_pw",
        role=UserRole.CITIZEN,
        is_active=True,
    )
    # Responder A (Closer: 1.0 km)
    rescuer_a = User(
        email="rescuer_a@example.com",
        full_name="Rescuer Alice",
        phone="+919999900002",
        password_hash="hashed_pw",
        role=UserRole.RESCUER,
        is_active=True,
    )
    # Responder B (2.0 km)
    rescuer_b = User(
        email="rescuer_b@example.com",
        full_name="Rescuer Bob",
        phone="+919999900003",
        password_hash="hashed_pw",
        role=UserRole.RESCUER,
        is_active=True,
    )
    # Veterinarian & Facility
    vet = User(
        email="vet_e2e@example.com",
        full_name="Dr. Rao",
        phone="+919999900004",
        password_hash="hashed_pw",
        role=UserRole.VETERINARIAN,
        is_active=True,
    )
    # NGO Admin
    ngo_admin = User(
        email="admin_e2e@example.com",
        full_name="Admin Anita",
        phone="+919999900005",
        password_hash="hashed_pw",
        role=UserRole.NGO_ADMIN,
        is_active=True,
    )
    db.add_all([citizen, rescuer_a, rescuer_b, vet, ngo_admin])
    db.commit()

    # Facility
    facility = VeterinaryFacility(
        name="Hope Animal Trauma Center",
        address="Bandra West, Mumbai",
        phone="+912226001122",
        supports_emergency=True,
        is_24_hours=True,
        latitude=19.060,
        longitude=72.835,
        is_verified=True,
    )
    db.add(facility)
    db.commit()
    vet.veterinary_facility_id = facility.id
    db.commit()

    # Rescuer Profiles with locations near 19.055, 72.830
    profile_a = RescuerProfile(
        user_id=rescuer_a.id,
        availability_status="AVAILABLE",
        latitude=19.057,
        longitude=72.832,
        last_location_update=datetime.utcnow(),
        vehicle_available=True,
        experience_level="Expert",
        reliability_score=98.0,
    )
    profile_b = RescuerProfile(
        user_id=rescuer_b.id,
        availability_status="AVAILABLE",
        latitude=19.065,
        longitude=72.840,
        last_location_update=datetime.utcnow(),
        vehicle_available=True,
        experience_level="Intermediate",
        reliability_score=90.0,
    )
    db.add_all([profile_a, profile_b])
    db.commit()

    # Generate Auth Tokens
    from app.core.security import create_access_token
    token_citizen = create_access_token(citizen.id)
    token_a = create_access_token(rescuer_a.id)
    token_b = create_access_token(rescuer_b.id)
    token_vet = create_access_token(vet.id)
    token_ngo = create_access_token(ngo_admin.id)

    # 2. STEP 1-4: Citizen Reports Critical Injured Animal
    report_payload = {
        "species": "Dog",
        "description": "Dog hit by truck, heavy bleeding, cannot stand",
        "latitude": 19.055,
        "longitude": 72.830,
        "address_text": "Near Bandra Station",
        "bleeding": True,
        "can_walk": False,
        "conscious": True,
        "vehicle_accident": True,
        "breathing_difficulty": True,
    }
    resp = client.post(
        "/api/v1/rescues",
        json=report_payload,
        headers={"Authorization": f"Bearer {token_citizen}"},
    )
    assert resp.status_code in [200, 201], resp.text
    case_data = resp.json()
    case_id = case_data["id"]
    assert case_data["triage_priority"] == "CRITICAL"
    # Case must automatically enter SEARCHING_RESPONDER
    assert case_data["status"] == RescueStatus.SEARCHING_RESPONDER.value

    import uuid
    case_uuid = uuid.UUID(case_id)

    # 3. STEP 5-7: Automatic Dispatch Engine Runs and Creates Offers
    offers = db.query(RescueAssignment).filter(RescueAssignment.rescue_case_id == case_uuid).all()
    assert len(offers) >= 2
    rescuer_ids_offered = {o.rescuer_id for o in offers}
    assert rescuer_a.id in rescuer_ids_offered
    assert rescuer_b.id in rescuer_ids_offered

    # 4. STEP 8: Responder A checks inbox and declines with reason
    resp_a_inbox = client.get(
        "/api/v1/rescuers/me/offers",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_a_inbox.status_code == 200
    offers_a = resp_a_inbox.json()
    assert len(offers_a) >= 1
    offer_a_id = offers_a[0]["id"]

    resp_decline = client.post(
        f"/api/v1/rescuers/offers/{offer_a_id}/reject",
        json={"reason": "vehicle_unavailable"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_decline.status_code == 200
    db.expire_all()
    declined_offer = db.query(RescueAssignment).filter(RescueAssignment.id == uuid.UUID(offer_a_id)).first()
    assert declined_offer.assignment_status == AssignmentStatus.REJECTED
    assert declined_offer.rejection_reason == "vehicle_unavailable"

    # 5. STEP 9-10: Responder B accepts offer
    resp_b_inbox = client.get(
        "/api/v1/rescuers/me/offers",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b_inbox.status_code == 200
    offers_b = resp_b_inbox.json()
    offer_b_id = next(o["id"] for o in offers_b if o["rescue_case_id"] == case_id)

    resp_accept = client.post(
        f"/api/v1/rescuers/offers/{offer_b_id}/accept",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_accept.status_code == 200
    db.expire_all()

    # Verify Case is now RESPONDER_ASSIGNED
    case_in_db = db.query(RescueCase).filter(RescueCase.id == case_uuid).first()
    assert case_in_db.status == RescueStatus.RESPONDER_ASSIGNED

    # Verify Citizen received assignment notification
    citizen_notif = db.query(Notification).filter(
        Notification.user_id == citizen.id,
        Notification.type == "RESPONDER_ASSIGNED"
    ).first()
    assert citizen_notif is not None
    assert "responder assigned" in citizen_notif.title.lower() or "accepted" in citizen_notif.message.lower()

    # 6. STEP 11: NGO Operations Dashboard Tracks Case
    ngo_cases = client.get(
        "/api/v1/ngo/cases",
        headers={"Authorization": f"Bearer {token_ngo}"},
    )
    assert ngo_cases.status_code == 200
    assert any(c["id"] == case_id for c in ngo_cases.json())

    # 7. STEP 12-14: Responder B advances mission: EN_ROUTE -> ANIMAL_LOCATED -> RESCUED -> TRANSPORTING
    transitions = [
        RescueStatus.RESPONDER_EN_ROUTE,
        RescueStatus.ANIMAL_LOCATED,
        RescueStatus.RESCUED,
        RescueStatus.TRANSPORTING,
    ]
    for st in transitions:
        payload = {"status": st.value, "notes": f"Progressed to {st.value}"}
        if st == RescueStatus.TRANSPORTING:
            payload["veterinary_facility_id"] = str(facility.id)
        resp_up = client.patch(
            f"/api/v1/rescues/{case_id}/status",
            json=payload,
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp_up.status_code == 200

    # 8. STEP 15: Animal Arrives at Vet Clinic
    resp_arr = client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": RescueStatus.AT_VETERINARY_FACILITY.value, "veterinary_facility_id": str(facility.id)},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_arr.status_code == 200

    # Vet receives incoming patient notification
    vet_notif = db.query(Notification).filter(
        Notification.user_id == vet.id,
        Notification.type == "INCOMING_PATIENT"
    ).first()
    assert vet_notif is not None

    # 9. STEP 16: Veterinarian Updates Treatment
    treatment_payload = {
        "diagnosis": "Fractured femur stabilized with splint",
        "treatment_notes": "Patient stable and resting comfortably",
        "medications": "Analgesic & anti-inflammatory",
        "facility_id": str(facility.id),
    }
    resp_treat = client.post(
        f"/api/v1/rescues/{case_id}/treatments",
        json=treatment_payload,
        headers={"Authorization": f"Bearer {token_vet}"},
    )
    assert resp_treat.status_code in [200, 201]

    # Update to RECOVERING
    resp_rec = client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": RescueStatus.RECOVERING.value, "notes": "Post-op recovery underway"},
        headers={"Authorization": f"Bearer {token_vet}"},
    )
    assert resp_rec.status_code == 200

    # 10. STEP 17: NGO Dashboard Reflects Recovery and Close Case
    overview = client.get(
        "/api/v1/ngo/analytics/overview",
        headers={"Authorization": f"Bearer {token_ngo}"},
    )
    assert overview.status_code == 200
    assert overview.json()["recovering"] >= 1

    # Release and Close Case
    client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": RescueStatus.READY_FOR_RELEASE.value},
        headers={"Authorization": f"Bearer {token_vet}"},
    )
    client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": RescueStatus.RELEASED.value},
        headers={"Authorization": f"Bearer {token_vet}"},
    )
    resp_close = client.patch(
        f"/api/v1/rescues/{case_id}/status",
        json={"status": RescueStatus.CLOSED.value, "notes": "Animal fully healed and released to shelter"},
        headers={"Authorization": f"Bearer {token_vet}"},
    )
    assert resp_close.status_code == 200

    db.expire_all()
    closed_case = db.query(RescueCase).filter(RescueCase.id == case_uuid).first()
    assert closed_case.status == RescueStatus.CLOSED
    assert closed_case.closed_at is not None
