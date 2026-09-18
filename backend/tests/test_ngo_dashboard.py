import pytest
import uuid
from app.models.user import User
from app.models.organization import Organization
from app.models.audit_log import AuditLog
from app.core.constants import UserRole, OrganizationType
from app.core.security import get_password_hash, create_access_token

@pytest.fixture
def ngo_admin_user(db):
    org = Organization(
        name="Mumbai Animal Welfare Society",
        organization_type=OrganizationType.NGO,
        phone="+912221234567",
        email="info@maws.org"
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    user = User(
        full_name="NGO Ops Director",
        email=f"ngo_{uuid.uuid4().hex[:6]}@maws.org",
        phone=f"+9194{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass123"),
        role=UserRole.NGO_ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def ngo_admin_token(ngo_admin_user):
    return create_access_token(ngo_admin_user.id)

def test_ngo_dashboard_authorization(client, citizen_token, rescuer_token, ngo_admin_token, admin_token):
    """Ensure citizens and rescuers cannot access NGO routes, while NGO and Super Admins can."""
    # Citizen -> 403
    cit_res = client.get("/api/v1/ngo/analytics/overview", headers={"Authorization": f"Bearer {citizen_token}"})
    assert cit_res.status_code == 403

    # Rescuer -> 403
    res_res = client.get("/api/v1/ngo/analytics/overview", headers={"Authorization": f"Bearer {rescuer_token}"})
    assert res_res.status_code == 403

    # NGO Admin -> 200
    ngo_res = client.get("/api/v1/ngo/analytics/overview", headers={"Authorization": f"Bearer {ngo_admin_token}"})
    assert ngo_res.status_code == 200
    kpis = ngo_res.json()
    assert "active_cases" in kpis
    assert "critical_cases" in kpis

    # Super Admin -> 200
    sup_res = client.get("/api/v1/ngo/analytics/overview", headers={"Authorization": f"Bearer {admin_token}"})
    assert sup_res.status_code == 200

def test_ngo_case_action_and_audit_logging(client, citizen_token, ngo_admin_token, db):
    """Ensure administrative actions create structured audit records."""
    # Create a case
    create_res = client.post(
        "/api/v1/rescues",
        json={"species": "Dog", "latitude": 19.0760, "longitude": 72.8777},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    case_id = create_res.json()["id"]

    # Claim case first (unassigned cases must be claimed before actions)
    claim_res = client.post(
        f"/api/v1/ngo/cases/{case_id}/claim",
        headers={"Authorization": f"Bearer {ngo_admin_token}"}
    )
    assert claim_res.status_code == 200

    # NGO Admin triggers cancel action
    action_res = client.post(
        f"/api/v1/ngo/cases/{case_id}/actions",
        json={"action": "cancel", "reason": "Duplicate citizen report"},
        headers={"Authorization": f"Bearer {ngo_admin_token}"}
    )
    assert action_res.status_code == 200

    # Verify audit log was created
    audit = db.query(AuditLog).filter(
        AuditLog.entity == "rescue_case",
        AuditLog.entity_id == uuid.UUID(case_id),
        AuditLog.action.in_(["CANCEL", "ADMIN_CANCEL"])
    ).first()
    assert audit is not None
    assert audit.action in ["CANCEL", "ADMIN_CANCEL"]
    assert audit.new_value["reason"] == "Duplicate citizen report"
