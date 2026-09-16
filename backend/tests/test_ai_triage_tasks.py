import pytest
import uuid
from unittest.mock import patch
from app.models.rescue_case import RescueCase
from app.models.animal_image import AnimalImage
from app.models.triage_assessment import TriageAssessment
from app.models.rescue_status_history import RescueStatusHistory
from app.models.notification import Notification
from app.core.constants import RescuePriority, RescueStatus, UserRole
from app.tasks.ai_triage_tasks import perform_ai_triage_task
from app.config import settings

@pytest.fixture
def sample_rescue_case_with_image(db, citizen_user):
    case = RescueCase(
        case_number=f"PR-TEST-{uuid.uuid4().hex[:6].upper()}",
        reporter_id=citizen_user.id,
        species="Dog",
        description="Dog injured on road",
        latitude=19.0760,
        longitude=72.8777,
        bleeding=False,
        can_walk=True,
        conscious=True,
        vehicle_accident=False,
        breathing_difficulty=False,
        triage_score=20,
        triage_priority=RescuePriority.GENERAL,
        triage_reason="Standard rescue intake",
        status=RescueStatus.SEARCHING_RESPONDER,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    img = AnimalImage(
        rescue_case_id=case.id,
        image_url="rescues/dog_test.jpg",
        image_type="REPORT",
        uploaded_by=citizen_user.id,
    )
    db.add(img)
    db.commit()
    db.refresh(img)

    return case, img

def test_task_skipped_when_ai_triage_disabled(db, sample_rescue_case_with_image, monkeypatch):
    case, img = sample_rescue_case_with_image
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", False)

    result = perform_ai_triage_task(
        str(case.id), str(img.id), db_session=db
    )

    assert result["status"] == "SKIPPED"
    assert result["reason"] == "Feature disabled"

    # Verify assessment record created with SKIPPED
    assessment = db.query(TriageAssessment).filter(TriageAssessment.rescue_case_id == case.id).first()
    assert assessment is not None
    assert assessment.status == "SKIPPED"
    assert assessment.suggested_priority == RescuePriority.GENERAL

    # Verify case priority is untouched
    db.refresh(case)
    assert case.triage_priority == RescuePriority.GENERAL

def test_task_executes_with_mock_provider_and_escalates(db, sample_rescue_case_with_image, ngo_admin_user, monkeypatch):
    case, img = sample_rescue_case_with_image
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "AI_TRIAGE_MIN_CONFIDENCE", 0.70)

    # Mock get_image_bytes to return dummy bytes
    with patch("app.services.storage_service.storage_service.get_image_bytes", return_value=b"valid_dummy_image"):
        result = perform_ai_triage_task(
            str(case.id), str(img.id), db_session=db
        )

    assert result["status"] == "COMPLETED"

    # Verify assessment record
    assessment = db.query(TriageAssessment).filter(TriageAssessment.rescue_case_id == case.id).first()
    assert assessment is not None
    assert assessment.status == "COMPLETED"
    assert assessment.confidence >= 0.70
    assert assessment.suggested_priority is not None
    assert assessment.visible_signs is not None

    # Verify case priority was updated according to fusion
    db.refresh(case)
    assert case.triage_priority == RescuePriority(result["final_priority"])

    # If escalated, status history was logged
    if result["escalated"]:
        history = db.query(RescueStatusHistory).filter(RescueStatusHistory.rescue_case_id == case.id).first()
        assert history is not None
        assert "AI visual triage escalated priority" in history.notes

def test_task_idempotency_prevents_duplicate_assessments(db, sample_rescue_case_with_image, monkeypatch):
    case, img = sample_rescue_case_with_image
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")

    with patch("app.services.storage_service.storage_service.get_image_bytes", return_value=b"valid_dummy_image"):
        res1 = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)
        assert res1["status"] == "COMPLETED"

        # Second call for the same case and model version
        res2 = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)
        assert res2["status"] == "ALREADY_COMPLETED"

    # Verify only one assessment exists in database
    count = db.query(TriageAssessment).filter(TriageAssessment.rescue_case_id == case.id).count()
    assert count == 1

def test_task_handles_storage_error_gracefully(db, sample_rescue_case_with_image, monkeypatch):
    case, img = sample_rescue_case_with_image
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")

    # Simulate storage error
    with patch("app.services.storage_service.storage_service.get_image_bytes", side_effect=RuntimeError("S3 Access Denied")):
        result = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)

    assert result["status"] == "FAILED"
    assert result["error"] == "Image load error"

    assessment = db.query(TriageAssessment).filter(TriageAssessment.rescue_case_id == case.id).first()
    assert assessment is not None
    assert assessment.status == "FAILED"
    assert assessment.sanitized_error_code == "IMAGE_LOAD_ERROR"

    # Case priority must remain unchanged
    db.refresh(case)
    assert case.triage_priority == RescuePriority.GENERAL

def test_task_case_not_found(db):
    result = perform_ai_triage_task(str(uuid.uuid4()), None, db_session=db)
    assert result["status"] == "ABORTED"
    assert result["reason"] == "Case not found"

def test_task_no_image_attached(db, citizen_user, monkeypatch):
    case = RescueCase(
        case_number="PR-NO-IMAGE-TEST",
        reporter_id=citizen_user.id,
        species="Dog",
        description="Dog with no photo",
        latitude=19.0760,
        longitude=72.8777,
        status=RescueStatus.SEARCHING_RESPONDER,
    )
    db.add(case)
    db.commit()

    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")

    result = perform_ai_triage_task(str(case.id), None, db_session=db)
    assert result["status"] == "SKIPPED"
    assert result["reason"] == "No image"

def test_task_escalates_to_critical_and_notifies_admins(db, sample_rescue_case_with_image, ngo_admin_user, monkeypatch):
    case, img = sample_rescue_case_with_image
    case.status = RescueStatus.SEARCHING_RESPONDER
    db.commit()

    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "AI_TRIAGE_MIN_CONFIDENCE", 0.70)

    from app.ai.schemas import AITriageResult
    critical_result = AITriageResult(
        suggested_priority=RescuePriority.CRITICAL,
        score=98,
        confidence=0.95,
        visible_signs=["Arterial blood spurting", "Massive open fracture"],
        explanation="Life threatening acute trauma detected.",
    )

    with patch("app.services.storage_service.storage_service.get_image_bytes", return_value=b"valid_image"), \
         patch("app.ai.mock.MockVisionTriageProvider.assess", return_value=critical_result):
        result = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)

    assert result["status"] == "COMPLETED"
    assert result["escalated"] is True
    assert result["final_priority"] == "CRITICAL"

    # Verify notification created for NGO Admin
    notif = db.query(Notification).filter(
        Notification.user_id == ngo_admin_user.id,
        Notification.type == "CRITICAL_ALERT"
    ).first()
    assert notif is not None
    assert "AI ESCALATION to CRITICAL" in notif.title

def test_task_handles_provider_assessment_exception(db, sample_rescue_case_with_image, monkeypatch):
    case, img = sample_rescue_case_with_image
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")

    with patch("app.services.storage_service.storage_service.get_image_bytes", return_value=b"valid_image"), \
         patch("app.ai.mock.MockVisionTriageProvider.assess", side_effect=RuntimeError("Provider Timeout")):
        result = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)

    assert result["status"] == "FAILED"
    assert result["error"] == "Provider error"

    assessment = db.query(TriageAssessment).filter(TriageAssessment.rescue_case_id == case.id).first()
    assert assessment.status == "FAILED"
    assert assessment.sanitized_error_code == "PROVIDER_ERROR"

