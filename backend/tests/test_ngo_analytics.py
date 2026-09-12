import pytest
import uuid
from datetime import datetime, timedelta

from app.models.user import User
from app.models.organization import Organization
from app.models.rescue_case import RescueCase
from app.models.rescue_assignment import RescueAssignment
from app.models.rescuer_profile import RescuerProfile
from app.core.constants import UserRole, OrganizationType, RescuePriority, RescueStatus, AssignmentStatus, RescuerAvailability
from app.core.security import get_password_hash, create_access_token

@pytest.fixture
def analytics_test_setup(db):
    """Set up two isolated organizations with cases, assignments, and responders for analytics verification."""
    # Org A
    org_a = Organization(
        name="Kochi Rescue Alliance",
        organization_type=OrganizationType.NGO,
        email="contact@kochirall.org",
        phone="+919847000001",
        operating_region="Ernakulam District",
        description="Central animal emergency response network in Kochi",
    )
    db.add(org_a)
    db.commit()
    db.refresh(org_a)

    # Org B
    org_b = Organization(
        name="Calicut Animal Shield",
        organization_type=OrganizationType.NGO,
        email="info@calicutshield.org",
        phone="+919847000002",
        operating_region="Kozhikode District",
        description="Animal welfare network in Kozhikode",
    )
    db.add(org_b)
    db.commit()
    db.refresh(org_b)

    # Org A Admin
    admin_a = User(
        full_name="Amina Jacob (Org A)",
        email=f"amina_{uuid.uuid4().hex[:6]}@kochirall.org",
        phone=f"+9194{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass123"),
        role=UserRole.NGO_ADMIN,
        organization_id=org_a.id,
        is_active=True,
    )
    db.add(admin_a)

    # Org B Admin
    admin_b = User(
        full_name="Farhan Khan (Org B)",
        email=f"farhan_{uuid.uuid4().hex[:6]}@calicutshield.org",
        phone=f"+9194{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass123"),
        role=UserRole.NGO_ADMIN,
        organization_id=org_b.id,
        is_active=True,
    )
    db.add(admin_b)

    # Org A Responders
    rescuer_a = User(
        full_name="Vinod Kumar",
        phone=f"+9194{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass123"),
        role=UserRole.RESCUER,
        organization_id=org_a.id,
        is_active=True,
    )
    db.add(rescuer_a)
    db.commit()
    db.refresh(rescuer_a)

    profile_a = RescuerProfile(
        user_id=rescuer_a.id,
        organization_id=org_a.id,
        availability_status=RescuerAvailability.AVAILABLE,
        experience_level="Advanced",
        vehicle_available=True,
        latitude=9.9816,
        longitude=76.2999,
        last_location_update=datetime.utcnow(),
    )
    db.add(profile_a)

    # Citizen Reporter
    citizen = User(
        full_name="Citizen A",
        phone=f"+9194{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("pass123"),
        role=UserRole.CITIZEN,
        is_active=True,
    )
    db.add(citizen)
    db.commit()
    db.refresh(citizen)

    # Org A Case 1: Closed critical case
    case_a1 = RescueCase(
        case_number="PR-TEST-001",
        reporter_id=citizen.id,
        organization_id=org_a.id,
        species="Canine",
        description="Severe injury on road",
        latitude=9.9816,
        longitude=76.2999,
        address_text="Palarivattom, Kochi",
        triage_score=85,
        triage_priority=RescuePriority.CRITICAL,
        triage_reason="Open fracture with bleeding",
        status=RescueStatus.CLOSED,
        dispatch_attempt=1,
        dispatch_radius_km=5.0,
        created_at=datetime.utcnow() - timedelta(days=2),
        closed_at=datetime.utcnow() - timedelta(days=1),
    )
    db.add(case_a1)

    # Org A Case 2: Active under treatment case
    case_a2 = RescueCase(
        case_number="PR-TEST-002",
        reporter_id=citizen.id,
        organization_id=org_a.id,
        species="Feline",
        description="Trapped kitten",
        latitude=9.9820,
        longitude=76.3010,
        address_text="Kaloor, Kochi",
        triage_score=60,
        triage_priority=RescuePriority.URGENT,
        triage_reason="Hypothermia",
        status=RescueStatus.UNDER_TREATMENT,
        dispatch_attempt=2,
        dispatch_radius_km=10.0,
        created_at=datetime.utcnow() - timedelta(hours=6),
    )
    db.add(case_a2)

    # Org B Case: Unresolved case belonging to Org B
    case_b1 = RescueCase(
        case_number="PR-TEST-003",
        reporter_id=citizen.id,
        organization_id=org_b.id,
        species="Bovine",
        description="Calicut emergency",
        latitude=11.2588,
        longitude=75.7804,
        address_text="Mavoor Road, Kozhikode",
        triage_score=90,
        triage_priority=RescuePriority.CRITICAL,
        triage_reason="Hit by truck",
        status=RescueStatus.UNRESOLVED,
        dispatch_attempt=4,
        dispatch_radius_km=40.0,
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    db.add(case_b1)
    db.commit()
    db.refresh(case_a1)
    db.refresh(case_a2)

    # Assignments for Case A1 (to record response times)
    assign_a1 = RescueAssignment(
        rescue_case_id=case_a1.id,
        rescuer_id=rescuer_a.id,
        offered_at=case_a1.created_at,
        accepted_at=case_a1.created_at + timedelta(minutes=15),
        assignment_status=AssignmentStatus.ACCEPTED,
        dispatch_score=88.5,
        distance_km=2.3,
    )
    db.add(assign_a1)
    db.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "token_a": create_access_token(admin_a.id),
        "token_b": create_access_token(admin_b.id),
    }

def test_ngo_overview_kpis_calculation_and_scoping(client, analytics_test_setup):
    """Verify overview KPIs are strictly tenant-scoped with real calculations and zero fake fallbacks."""
    token_a = analytics_test_setup["token_a"]
    res_a = client.get("/api/v1/ngo/analytics/overview", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    data_a = res_a.json()

    # Org A has 2 cases: 1 CLOSED, 1 UNDER_TREATMENT
    assert data_a["total_cases"] == 2
    assert data_a["active_cases"] == 1
    assert data_a["critical_cases"] == 0  # The only critical case is CLOSED
    assert data_a["urgent_cases"] == 1
    assert data_a["under_treatment"] == 1
    assert data_a["responders_available"] == 1
    assert data_a["completion_rate_pct"] == 50.0  # 1 closed out of 2 non-cancelled = 50%
    assert data_a["avg_response_minutes"] == 15.0  # 15 minutes latency on case A1
    assert data_a["unresolved_cases"] == 0  # Org B's unresolved case must NOT leak here

    # Org B Admin should only see their own 1 case
    token_b = analytics_test_setup["token_b"]
    res_b = client.get("/api/v1/ngo/analytics/overview", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["total_cases"] == 1
    assert data_b["unresolved_cases"] == 1

def test_ngo_response_time_analytics_periods(client, analytics_test_setup):
    """Verify response time trends return daily groupings for 7d, 30d, 90d periods."""
    token_a = analytics_test_setup["token_a"]

    # 30d period
    res_30 = client.get("/api/v1/ngo/analytics/response-times?period=30d", headers={"Authorization": f"Bearer {token_a}"})
    assert res_30.status_code == 200
    points_30 = res_30.json()
    assert len(points_30) == 30
    assert any(p["cases"] > 0 for p in points_30)

    # 7d period
    res_7 = client.get("/api/v1/ngo/analytics/response-times?period=7d", headers={"Authorization": f"Bearer {token_a}"})
    assert res_7.status_code == 200
    points_7 = res_7.json()
    assert len(points_7) == 7

def test_ngo_rescue_outcomes_breakdown(client, analytics_test_setup):
    """Verify outcome aggregation, success rates, and veterinary handoff rate formulas."""
    token_a = analytics_test_setup["token_a"]
    res = client.get("/api/v1/ngo/analytics/outcomes", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    outcomes = res.json()

    assert outcomes["total_cases"] == 2
    assert outcomes["outcomes"]["CLOSED"] == 1
    assert outcomes["outcomes"]["UNDER_TREATMENT"] == 1
    assert outcomes["outcomes"]["UNRESOLVED"] == 0
    assert outcomes["rescue_success_rate"] == 50.0
    assert outcomes["veterinary_handoff_rate"] == 50.0  # 1 under treatment

def test_ngo_incident_hotspots_and_insights(client, analytics_test_setup):
    """Verify geographic hotspot clustering and operational insights."""
    token_a = analytics_test_setup["token_a"]

    # Hotspots
    res_hotspots = client.get("/api/v1/ngo/analytics/hotspots", headers={"Authorization": f"Bearer {token_a}"})
    assert res_hotspots.status_code == 200
    hotspots = res_hotspots.json()
    assert len(hotspots) > 0
    # Must only contain Kochi coordinates (~9.98), NOT Calicut (~11.25)
    for h in hotspots:
        assert h["latitude"] < 10.5

    # Insights
    res_insights = client.get("/api/v1/ngo/analytics/insights", headers={"Authorization": f"Bearer {token_a}"})
    assert res_insights.status_code == 200
    insights = res_insights.json()
    assert "busiest_day" in insights
    assert "top_rescue_area" in insights
    assert insights["responder_acceptance_rate_pct"] == 100.0  # 1 offer, 1 accepted
    assert insights["escalation_rate_pct"] == 50.0  # 1 out of 2 cases had dispatch_attempt > 1
