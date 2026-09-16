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


def test_retry_triage_cross_tenant_ngo_denied(client, db, case_with_completed_triage):
    """An NGO Admin from Org B cannot retry triage for a case belonging to Org A."""
    from app.models.organization import Organization
    from app.models.user import User
    from app.core.constants import UserRole, OrganizationType

    case, _ = case_with_completed_triage

    other_org = Organization(
        name="Other NGO Shelter",
        organization_type=OrganizationType.NGO,
        email="other_ngo@example.com",
        phone="+912226009999",
        operating_region="Mumbai South",
        verification_status=True,
    )
    db.add(other_org)
    db.commit()
    db.refresh(other_org)

    other_admin = User(
        full_name="Other NGO Admin",
        email=f"other_admin_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9193{uuid.uuid4().hex[:8]}",
        password_hash="dummy_hash_for_test",
        role=UserRole.NGO_ADMIN,
        organization_id=other_org.id,
        is_active=True,
        is_verified=True,
    )
    db.add(other_admin)
    db.commit()
    db.refresh(other_admin)

    other_token = create_access_token(other_admin.id)

    res = client.post(
        f"/api/v1/rescues/{case.id}/triage/retry?force=true",
        headers={"Authorization": f"Bearer {other_token}"}
    )
    assert res.status_code == 403
    assert "Cross-tenant access forbidden" in str(res.json())


def test_retry_triage_ngo_null_organization_denied(client, db, case_with_completed_triage):
    """An NGO Admin without an assigned organization is denied access to retry."""
    from app.models.user import User
    from app.core.constants import UserRole

    case, _ = case_with_completed_triage

    unattached_admin = User(
        full_name="Unattached NGO Admin",
        email=f"unattached_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9192{uuid.uuid4().hex[:8]}",
        password_hash="dummy_hash_for_test",
        role=UserRole.NGO_ADMIN,
        organization_id=None,
        is_active=True,
        is_verified=True,
    )
    db.add(unattached_admin)
    db.commit()
    db.refresh(unattached_admin)

    unattached_token = create_access_token(unattached_admin.id)

    res = client.post(
        f"/api/v1/rescues/{case.id}/triage/retry?force=true",
        headers={"Authorization": f"Bearer {unattached_token}"}
    )
    assert res.status_code == 403
    assert "associated with an organization" in str(res.json())


def test_retry_triage_case_null_organization_denied_for_ngo(client, db, citizen_user, ngo_admin_token):
    """An unassigned case (no organization) cannot be retried by an NGO Admin."""
    case = RescueCase(
        case_number="PR-NO-ORG",
        reporter_id=citizen_user.id,
        organization_id=None,
        species="Dog",
        description="Stray dog without assigned org",
        latitude=19.0760,
        longitude=72.8777,
        status=RescueStatus.SEARCHING_RESPONDER,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    img = AnimalImage(
        rescue_case_id=case.id,
        image_url="rescues/dog_no_org.jpg",
        image_type="REPORT",
        uploaded_by=citizen_user.id,
    )
    db.add(img)
    db.commit()

    res = client.post(
        f"/api/v1/rescues/{case.id}/triage/retry?force=true",
        headers={"Authorization": f"Bearer {ngo_admin_token}"}
    )
    assert res.status_code == 403


def test_retry_triage_super_admin_global_success(client, db, citizen_user, admin_token):
    """Super Admin has global retry authority, including cases without an organization."""
    case = RescueCase(
        case_number="PR-SUPER-RETRY",
        reporter_id=citizen_user.id,
        organization_id=None,
        species="Dog",
        description="Critical stray needing assessment",
        latitude=19.0760,
        longitude=72.8777,
        status=RescueStatus.SEARCHING_RESPONDER,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    img = AnimalImage(
        rescue_case_id=case.id,
        image_url="rescues/super_dog.jpg",
        image_type="REPORT",
        uploaded_by=citizen_user.id,
    )
    db.add(img)
    db.commit()

    with patch("app.tasks.ai_triage_tasks.perform_ai_triage_task.delay") as mock_delay:
        res = client.post(
            f"/api/v1/rescues/{case.id}/triage/retry?force=true",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        mock_delay.assert_called_once()


