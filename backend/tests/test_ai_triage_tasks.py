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
    monkeypatch.setattr(perform_ai_triage_task.request, "retries", 2)

    # Simulate storage error
    with patch("app.services.storage_service.storage_service.get_image_bytes", side_effect=RuntimeError("S3 Access Denied")):
        result = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)

    assert result["status"] == "FAILED"
    assert result["error"] == "IMAGE_LOAD_ERROR"

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
    assert result["reason"] == "CASE_NOT_FOUND"

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
    case.organization_id = ngo_admin_user.organization_id
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
    monkeypatch.setattr(perform_ai_triage_task.request, "retries", 2)

    from app.ai.base import AITriageException
    with patch("app.services.storage_service.storage_service.get_image_bytes", return_value=b"valid_image"), \
         patch("app.ai.mock.MockVisionTriageProvider.assess", side_effect=AITriageException("Provider Error")):
        result = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)

    assert result["status"] == "FAILED"
    assert result["error"] == "PROVIDER_ERROR"

    assessment = db.query(TriageAssessment).filter(TriageAssessment.rescue_case_id == case.id).first()
    assert assessment is not None
    assert assessment.status == "FAILED"
    assert assessment.sanitized_error_code == "PROVIDER_ERROR"

def test_task_aborts_when_image_belongs_to_different_case(db, citizen_user):
    case1 = RescueCase(
        case_number="PR-CASE-1",
        reporter_id=citizen_user.id,
        species="Cat",
        latitude=19.0760,
        longitude=72.8777,
        status=RescueStatus.REPORTED,
    )
    case2 = RescueCase(
        case_number="PR-CASE-2",
        reporter_id=citizen_user.id,
        species="Dog",
        latitude=19.0760,
        longitude=72.8777,
        status=RescueStatus.REPORTED,
    )
    db.add_all([case1, case2])
    db.commit()

    img2 = AnimalImage(
        rescue_case_id=case2.id,
        image_url="rescues/case2_image.jpg",
        image_type="REPORT",
        uploaded_by=citizen_user.id,
    )
    db.add(img2)
    db.commit()

    result = perform_ai_triage_task(str(case1.id), str(img2.id), db_session=db)
    assert result["status"] == "ABORTED"
    assert result["reason"] == "IMAGE_CASE_MISMATCH"

    # Verify no assessment was created for case1
    assert db.query(TriageAssessment).filter(TriageAssessment.rescue_case_id == case1.id).count() == 0

def test_task_critical_escalation_tenant_notification_scoping(db, sample_rescue_case_with_image, test_org, ngo_admin_user, admin_user, monkeypatch):
    case, img = sample_rescue_case_with_image
    case.organization_id = test_org.id
    case.status = RescueStatus.SEARCHING_RESPONDER
    db.commit()

    from app.models.user import User
    from app.models.organization import Organization
    from app.core.constants import OrganizationType
    other_org = Organization(
        name="Other Distant NGO",
        organization_type=OrganizationType.NGO,
        email="other@ngo.org",
        phone="+919988776655",
        operating_region="Pune",
        verification_status=True,
    )
    db.add(other_org)
    db.commit()

    other_admin = User(
        full_name="Other NGO Admin",
        email=f"other_admin_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9193{uuid.uuid4().hex[:8]}",
        password_hash="dummy_hash",
        role=UserRole.NGO_ADMIN,
        organization_id=other_org.id,
        is_active=True,
        is_verified=True,
    )
    inactive_admin = User(
        full_name="Inactive NGO Admin",
        email=f"inactive_admin_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9192{uuid.uuid4().hex[:8]}",
        password_hash="dummy_hash",
        role=UserRole.NGO_ADMIN,
        organization_id=test_org.id,
        is_active=False,
        is_verified=True,
    )
    db.add_all([other_admin, inactive_admin])
    db.commit()

    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "AI_TRIAGE_MIN_CONFIDENCE", 0.70)

    from app.ai.schemas import AITriageResult
    critical_result = AITriageResult(
        suggested_priority=RescuePriority.CRITICAL,
        score=99,
        confidence=0.98,
        visible_signs=["Life threatening bleed"],
        explanation="Severe trauma detected.",
    )

    with patch("app.services.storage_service.storage_service.get_image_bytes", return_value=b"valid_image"), \
         patch("app.ai.mock.MockVisionTriageProvider.assess", return_value=critical_result):
        result = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)

    assert result["status"] == "COMPLETED"
    assert result["escalated"] is True
    assert result["final_priority"] == "CRITICAL"

    # Recipient verification:
    # 1. Org A admin received alert
    notif_org_admin = db.query(Notification).filter(
        Notification.user_id == ngo_admin_user.id,
        Notification.type == "CRITICAL_ALERT",
        Notification.rescue_case_id == case.id,
    ).first()
    assert notif_org_admin is not None

    # 2. Super Admin received alert
    notif_super_admin = db.query(Notification).filter(
        Notification.user_id == admin_user.id,
        Notification.type == "CRITICAL_ALERT",
        Notification.rescue_case_id == case.id,
    ).first()
    assert notif_super_admin is not None

    # 3. Other Org Admin NEVER received alert
    notif_other = db.query(Notification).filter(
        Notification.user_id == other_admin.id,
        Notification.rescue_case_id == case.id,
    ).first()
    assert notif_other is None

    # 4. Inactive Admin NEVER received alert
    notif_inactive = db.query(Notification).filter(
        Notification.user_id == inactive_admin.id,
        Notification.rescue_case_id == case.id,
    ).first()
    assert notif_inactive is None

def test_task_handles_concurrent_race_integrity_error(db, sample_rescue_case_with_image, monkeypatch):
    case, img = sample_rescue_case_with_image
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")

    # Pre-create an assessment for this case and mock provider (matching MockVisionTriageProvider constants)
    existing = TriageAssessment(
        rescue_case_id=case.id,
        animal_image_id=img.id,
        source="IMAGE_AI",
        status="COMPLETED",
        suggested_priority=RescuePriority.URGENT,
        score=75,
        confidence=0.85,
        provider="mock",
        model_name="pawreach-vision-mock",
        model_version="test-v1.0",
    )
    db.add(existing)
    db.commit()

    # Now call perform_ai_triage_task; should detect already completed idempotently without re-running
    res = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)
    assert res["status"] == "ALREADY_COMPLETED"
    assert res["assessment_id"] == str(existing.id)


def test_task_enforces_timeout_and_records_provider_timeout(db, sample_rescue_case_with_image, monkeypatch):
    """Ensure AI_TRIAGE_TIMEOUT_SECONDS constrains execution and produces PROVIDER_TIMEOUT."""
    case, img = sample_rescue_case_with_image
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "AI_TRIAGE_TIMEOUT_SECONDS", 0.1)

    def slow_assess(image_bytes, context, *args, **kwargs):
        from app.ai.base import AITriageTimeoutException
        raise AITriageTimeoutException("Provider assessment timed out after 0.1 seconds.")

    with patch("app.services.storage_service.storage_service.get_image_bytes", return_value=b"valid_image"), \
         patch("app.ai.mock.MockVisionTriageProvider.assess", side_effect=slow_assess):
        result = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)

    assert result["status"] == "FAILED"
    assert result["error"] == "PROVIDER_TIMEOUT"

    assessment = db.query(TriageAssessment).filter(TriageAssessment.rescue_case_id == case.id).first()
    assert assessment is not None
    assert assessment.status == "FAILED"
    assert assessment.sanitized_error_code == "PROVIDER_TIMEOUT"
    assert "timed out" in assessment.explanation


def test_task_provider_timeout_does_not_downgrade_hard_rule_priority(db, sample_rescue_case_with_image, monkeypatch):
    """A timeout during AI triage must preserve existing deterministic rule priority without downgrade."""
    case, img = sample_rescue_case_with_image
    case.triage_priority = RescuePriority.URGENT
    case.triage_score = 70
    case.triage_reason = "Severe bleeding reported"
    db.commit()

    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "AI_TRIAGE_TIMEOUT_SECONDS", 0.05)

    def slow_assess(image_bytes, context, *args, **kwargs):
        from app.ai.base import AITriageTimeoutException
        raise AITriageTimeoutException("Provider assessment timed out")

    with patch("app.services.storage_service.storage_service.get_image_bytes", return_value=b"valid_image"), \
         patch("app.ai.mock.MockVisionTriageProvider.assess", side_effect=slow_assess):
        result = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)

    assert result["status"] == "FAILED"
    assert result["error"] == "PROVIDER_TIMEOUT"

    # Deterministic priority must remain completely invariant
    db.refresh(case)
    assert case.triage_priority == RescuePriority.URGENT
    assert case.triage_score == 70
    assert "Severe bleeding reported" in case.triage_reason


def test_task_sanitizes_unexpected_outer_exception(db, sample_rescue_case_with_image, monkeypatch):
    """Any unexpected exception must return sanitized UNEXPECTED_ERROR without leaking str(e)."""
    case, img = sample_rescue_case_with_image
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(perform_ai_triage_task.request, "retries", 2)

    with patch("app.services.storage_service.storage_service.get_image_bytes", side_effect=Exception("Database secret credentials redis://user:secret123@host:6379")):
        with patch.object(RescueCase, "images", side_effect=RuntimeError("internal redis password leak redis://pwd")):
            pass

    with patch("app.tasks.ai_triage_tasks.get_vision_triage_provider", side_effect=RuntimeError("redis://secret_token@host")):
        result = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)

    assert result["status"] == "ERROR"
    assert result["error"] == "UNEXPECTED_ERROR"
    assert "secret" not in str(result)
    assert "redis" not in str(result)


def test_task_transient_failure_raises_celery_retry(db, sample_rescue_case_with_image, monkeypatch):
    """Prove that a transient storage or provider failure raises Celery Retry instead of being swallowed."""
    from celery.exceptions import Retry
    case, img = sample_rescue_case_with_image
    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(perform_ai_triage_task.request, "retries", 0)

    # 1. Transient storage failure raises Celery Retry
    with patch("app.services.storage_service.storage_service.get_image_bytes", side_effect=RuntimeError("Transient storage drop")):
        with pytest.raises(Retry):
            perform_ai_triage_task(str(case.id), str(img.id), db_session=db)

    # 2. Transient provider failure raises Celery Retry
    from app.ai.base import AITriageException
    with patch("app.services.storage_service.storage_service.get_image_bytes", return_value=b"valid_image"), \
         patch("app.ai.mock.MockVisionTriageProvider.assess", side_effect=AITriageException("Temporary API glitch")):
        with pytest.raises(Retry):
            perform_ai_triage_task(str(case.id), str(img.id), db_session=db)


def test_task_provider_context_contains_no_pii_gps_or_case_uuid(db, sample_rescue_case_with_image, monkeypatch):
    """Verify provider context minimizes data: only species, NO case_id, reporter PII, or GPS coordinates."""
    case, img = sample_rescue_case_with_image
    case.species = "Canine"
    db.commit()

    monkeypatch.setattr(settings, "AI_TRIAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TRIAGE_PROVIDER", "mock")
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")

    captured_contexts = []
    def recording_assess(image_bytes, context, *args, **kwargs):
        captured_contexts.append(context)
        from app.ai.schemas import AITriageResult
        return AITriageResult(
            suggested_priority=RescuePriority.URGENT,
            score=70,
            confidence=0.85,
            visible_signs=["abrasion"],
            explanation="Minor abrasion detected",
        )

    with patch("app.services.storage_service.storage_service.get_image_bytes", return_value=b"valid_image"), \
         patch("app.ai.mock.MockVisionTriageProvider.assess", side_effect=recording_assess):
        result = perform_ai_triage_task(str(case.id), str(img.id), db_session=db)

    assert result["status"] == "COMPLETED"
    assert len(captured_contexts) == 1
    ctx = captured_contexts[0]

    # Species is the only permissible triage input
    assert ctx == {"species": "Canine"}
    # Explicit assertions against PII, GPS, and case UUID
    assert "case_id" not in ctx
    assert "id" not in ctx
    assert "reporter_id" not in ctx
    assert "reporter_name" not in ctx
    assert "email" not in ctx
    assert "phone" not in ctx
    assert "latitude" not in ctx
    assert "longitude" not in ctx
    assert "address" not in ctx





