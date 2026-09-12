import pytest
from datetime import datetime, timedelta
import uuid

from app.models.user import User
from app.models.organization import Organization
from app.models.rescue_case import RescueCase
from app.models.rescue_assignment import RescueAssignment
from app.models.rescue_status_history import RescueStatusHistory
from app.core.constants import UserRole, RescueStatus, RescuePriority, AssignmentStatus
from app.core.security import create_access_token

@pytest.fixture
def contract_setup(db):
    org = Organization(
        id=uuid.uuid4(),
        name="Contract Testing NGO",
        organization_type="NGO",
        email="contracts@ngo.org",
        phone="+919876543210"
    )
    db.add(org)
    db.commit()

    admin = User(
        id=uuid.uuid4(),
        email="ngo_contract_admin@pawsos.org",
        password_hash="hashed_contract_pw",
        full_name="Contract Admin",
        phone="+919876543211",
        role=UserRole.NGO_ADMIN,
        organization_id=org.id,
        is_active=True
    )
    db.add(admin)
    db.commit()

    rescuer = User(
        id=uuid.uuid4(),
        email="rescuer_contract@pawsos.org",
        password_hash="hashed_contract_pw",
        full_name="Contract Rescuer",
        phone="+919876543212",
        role=UserRole.RESCUER,
        organization_id=org.id,
        is_active=True
    )
    db.add(rescuer)
    db.commit()

    case = RescueCase(
        id=uuid.uuid4(),
        case_number="CASE-CONTRACT-001",
        reporter_id=admin.id,
        species="Canine",
        latitude=18.922,
        longitude=72.834,
        address_text="Colaba Causeway",
        status=RescueStatus.RESCUED,
        triage_priority=RescuePriority.CRITICAL,
        organization_id=org.id,
        created_at=datetime.utcnow() - timedelta(minutes=45),
    )
    db.add(case)
    db.commit()

    # Status history
    hist1 = RescueStatusHistory(
        rescue_case_id=case.id,
        previous_status=None,
        new_status=RescueStatus.REPORTED,
        created_at=case.created_at
    )
    hist2 = RescueStatusHistory(
        rescue_case_id=case.id,
        previous_status=RescueStatus.REPORTED,
        new_status=RescueStatus.ANIMAL_LOCATED,
        created_at=case.created_at + timedelta(minutes=20)
    )
    hist3 = RescueStatusHistory(
        rescue_case_id=case.id,
        previous_status=RescueStatus.ANIMAL_LOCATED,
        new_status=RescueStatus.RESCUED,
        created_at=case.created_at + timedelta(minutes=35)
    )
    db.add_all([hist1, hist2, hist3])

    # Assignment
    assignment = RescueAssignment(
        rescue_case_id=case.id,
        rescuer_id=rescuer.id,
        offered_at=case.created_at + timedelta(minutes=2),
        accepted_at=case.created_at + timedelta(minutes=5),
        assignment_status=AssignmentStatus.ACCEPTED
    )
    db.add(assignment)
    db.commit()

    token = create_access_token(admin.id)
    return {"token": token, "org": org, "admin": admin, "case": case}

def test_contract_overview_kpis(client, contract_setup):
    headers = {"Authorization": f"Bearer {contract_setup['token']}"}
    resp = client.get("/api/v1/ngo/analytics/overview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Contract expectations matching frontend NGOOverviewKPIs interface
    expected_fields = {
        "active_cases": int,
        "critical_cases": int,
        "awaiting_responder": int,
        "responders_en_route": int,
        "under_treatment": int,
        "recovering": int,
        "avg_dispatch_seconds": (float, int),
        "average_response_minutes": (float, int),  # Canonical field
        "completion_rate_pct": (float, int),
        "responder_availability_pct": (float, int),
        "total_cases": int,
    }

    for field, exp_type in expected_fields.items():
        assert field in data, f"Missing expected contract field: {field}"
        assert isinstance(data[field], exp_type), f"Field '{field}' expected {exp_type}, got {type(data[field])}"

    # Also verify backward compatibility alias exists
    assert "avg_response_minutes" in data
    assert data["average_response_minutes"] == data["avg_response_minutes"]

def test_contract_response_times(client, contract_setup):
    headers = {"Authorization": f"Bearer {contract_setup['token']}"}
    resp = client.get("/api/v1/ngo/analytics/response-times?period=30d", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0

    # Validate ResponseTimeDataPoint contract
    sample = data[0]
    assert "date" in sample and isinstance(sample["date"], str)
    assert "average_response_minutes" in sample and isinstance(sample["average_response_minutes"], (float, int))
    assert "avg_response_minutes" in sample  # Backwards compatibility alias
    assert "cases" in sample and isinstance(sample["cases"], int)

def test_contract_outcomes(client, contract_setup):
    headers = {"Authorization": f"Bearer {contract_setup['token']}"}
    resp = client.get("/api/v1/ngo/analytics/outcomes", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Validate RescueOutcomesData contract
    assert "outcomes" in data and isinstance(data["outcomes"], dict)
    assert "rescue_success_rate" in data and isinstance(data["rescue_success_rate"], (float, int))
    assert "unresolved_rate" in data and isinstance(data["unresolved_rate"], (float, int))
    assert "veterinary_handoff_rate" in data and isinstance(data["veterinary_handoff_rate"], (float, int))
    assert "total_cases" in data and isinstance(data["total_cases"], int)
    assert "active_field_count" in data
    assert "rescued_transport_count" in data
    assert "successful_terminal_count" in data

def test_contract_hotspots(client, contract_setup):
    headers = {"Authorization": f"Bearer {contract_setup['token']}"}
    resp = client.get("/api/v1/ngo/analytics/hotspots?period=30d", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0

    # Validate HotspotItem contract
    sample = data[0]
    expected_hotspot_fields = {
        "latitude": (float, int),
        "longitude": (float, int),
        "incident_count": int,
        "critical_count": int,
        "top_species": str,
        "average_response_minutes": (float, int),
    }
    for field, exp_type in expected_hotspot_fields.items():
        assert field in sample, f"Missing hotspot contract field: {field}"
        assert isinstance(sample[field], exp_type)

def test_contract_insights(client, contract_setup):
    headers = {"Authorization": f"Bearer {contract_setup['token']}"}
    resp = client.get("/api/v1/ngo/analytics/insights", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Validate NGOInsightsData contract
    assert "responder_acceptance_rate_pct" in data and isinstance(data["responder_acceptance_rate_pct"], (float, int))
    assert "avg_dispatch_attempts" in data and isinstance(data["avg_dispatch_attempts"], (float, int))
    assert "escalation_rate_pct" in data and isinstance(data["escalation_rate_pct"], (float, int))
