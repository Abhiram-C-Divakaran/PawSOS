import pytest
import uuid
from unittest.mock import patch
from app.models.rescue_case import RescueCase
from app.models.animal_image import AnimalImage
from app.models.triage_assessment import TriageAssessment
from app.core.constants import RescuePriority, RescueStatus
from app.core.security import create_access_token
from app.tasks.celery_app import celery_app

# Set Celery to eager mode for API tests
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

@pytest.fixture
def case_with_completed_triage(db, citizen_user, test_org):
    case = RescueCase(
        case_number="PR-TRIAGE-001",
        reporter_id=citizen_user.id,
        organization_id=test_org.id,
        species="Cat",
        description="Cat trapped in drain",
        latitude=19.0760,
        longitude=72.8777,
        bleeding=True,
        can_walk=True,
        conscious=True,
        vehicle_accident=False,
        breathing_difficulty=False,
        triage_score=60,
        triage_priority=RescuePriority.URGENT,
        triage_reason="Visible bleeding reported",
        status=RescueStatus.SEARCHING_RESPONDER,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    img = AnimalImage(
        rescue_case_id=case.id,
        image_url="rescues/cat_drain.jpg",
        image_type="REPORT",
        uploaded_by=citizen_user.id,
    )
    db.add(img)
    db.commit()
    db.refresh(img)

    assessment = TriageAssessment(
        rescue_case_id=case.id,
        animal_image_id=img.id,
        source="HYBRID",
        status="COMPLETED",
        suggested_priority=RescuePriority.URGENT,
        score=65,
        confidence=0.88,
        visible_signs='["Active bleeding", "Minor abrasion"]',
        explanation="Localized bleeding without arterial compromise",
        provider="mock",
        model_name="pawreach-vision-safety",
        model_version="v1.0",
    )
    db.add(assessment)
    db.commit()

    return case, img

def test_get_triage_unauthenticated(client, case_with_completed_triage):
    case, _ = case_with_completed_triage
    res = client.get(f"/api/v1/rescues/{case.id}/triage")
    assert res.status_code == 401

def test_get_triage_not_found(client, citizen_token):
    random_id = uuid.uuid4()
    res = client.get(
        f"/api/v1/rescues/{random_id}/triage",
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    assert res.status_code == 404

def test_get_triage_authorized_citizen(client, case_with_completed_triage, citizen_token):
    case, _ = case_with_completed_triage
    res = client.get(
        f"/api/v1/rescues/{case.id}/triage",
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == str(case.id)
    assert data["case_number"] == "PR-TRIAGE-001"
    assert data["final_priority"] == "URGENT"
    assert data["rule_assessment"]["priority"] == "URGENT"
    assert "Visible bleeding reported" in data["rule_assessment"]["reasons"]
    assert data["ai_assessment"]["status"] == "COMPLETED"
    assert data["ai_assessment"]["confidence"] == 0.88
    assert "Active bleeding" in data["ai_assessment"]["visible_signs"]
    assert "does not constitute a veterinary medical diagnosis" in data["disclaimer"]

def test_get_triage_cross_tenant_denied(client, case_with_completed_triage, foster_token):
    """Another unrelated user without case access is rejected."""
    case, _ = case_with_completed_triage
    res = client.get(
        f"/api/v1/rescues/{case.id}/triage",
        headers={"Authorization": f"Bearer {foster_token}"}
    )
    assert res.status_code == 403

def test_get_triage_ngo_admin_authorized(client, case_with_completed_triage, ngo_admin_token):
    case, _ = case_with_completed_triage
    res = client.get(
        f"/api/v1/rescues/{case.id}/triage",
        headers={"Authorization": f"Bearer {ngo_admin_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == str(case.id)

def test_retry_triage_forbidden_for_citizen(client, case_with_completed_triage, citizen_token):
    case, _ = case_with_completed_triage
    res = client.post(
        f"/api/v1/rescues/{case.id}/triage/retry",
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    assert res.status_code == 403

def test_retry_triage_conflict_when_no_images(client, db, citizen_user, test_org, ngo_admin_token):
    case = RescueCase(
        case_number="PR-NO-IMG",
        reporter_id=citizen_user.id,
        organization_id=test_org.id,
        species="Dog",
        description="Dog without photo",
        latitude=19.0760,
        longitude=72.8777,
        status=RescueStatus.SEARCHING_RESPONDER,
    )
    db.add(case)
    db.commit()

    res = client.post(
        f"/api/v1/rescues/{case.id}/triage/retry",
        headers={"Authorization": f"Bearer {ngo_admin_token}"}
    )
    assert res.status_code == 409
    assert "No evidence image attached" in str(res.json())

def test_retry_triage_allowed_for_ngo_admin(client, case_with_completed_triage, ngo_admin_token):
    case, _ = case_with_completed_triage
    with patch("app.tasks.ai_triage_tasks.perform_ai_triage_task.delay") as mock_delay:
        res = client.post(
            f"/api/v1/rescues/{case.id}/triage/retry?force=true",
            headers={"Authorization": f"Bearer {ngo_admin_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "queued for execution" in data["message"]
        mock_delay.assert_called_once()

def test_retry_triage_case_not_found(client, ngo_admin_token):
    res = client.post(
        f"/api/v1/rescues/{uuid.uuid4()}/triage/retry",
        headers={"Authorization": f"Bearer {ngo_admin_token}"}
    )
    assert res.status_code == 404

def test_retry_triage_already_completed_without_force(client, case_with_completed_triage, ngo_admin_token):
    case, _ = case_with_completed_triage
    res = client.post(
        f"/api/v1/rescues/{case.id}/triage/retry?force=false",
        headers={"Authorization": f"Bearer {ngo_admin_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert "already completed" in data["message"]

def test_get_triage_with_plain_string_visible_signs(client, db, citizen_user, test_org, citizen_token):
    case = RescueCase(
        case_number="PR-SIGNS-TEST",
        reporter_id=citizen_user.id,
        organization_id=test_org.id,
        species="Dog",
        latitude=19.0760,
        longitude=72.8777,
        status=RescueStatus.SEARCHING_RESPONDER,
    )
    db.add(case)
    db.commit()

    assessment = TriageAssessment(
        rescue_case_id=case.id,
        source="IMAGE_AI",
        status="COMPLETED",
        visible_signs="Severe limping on right foreleg", # Plain string, not JSON array
        explanation="Mobility issue",
    )
    db.add(assessment)
    db.commit()

    res = client.get(
        f"/api/v1/rescues/{case.id}/triage",
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "Severe limping on right foreleg" in data["ai_assessment"]["visible_signs"]

