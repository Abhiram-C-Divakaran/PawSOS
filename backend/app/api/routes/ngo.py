from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.rescue_case import RescueCase
from app.models.rescue_assignment import RescueAssignment
from app.models.rescue_status_history import RescueStatusHistory
from app.models.rescuer_profile import RescuerProfile
from app.models.veterinary_facility import VeterinaryFacility
from app.models.audit_log import AuditLog
from app.core.permissions import RoleChecker
from app.core.constants import (
    UserRole,
    RescueStatus,
    RescuePriority,
    RescuerAvailability,
    AssignmentStatus,
)
from app.core.exceptions import ForbiddenException
from app.schemas.ngo import (
    NGOOverviewKPIs,
    HotspotItem,
    NGOResponderSummary,
    NGOResponderStatusUpdate,
    NGOCaseActionRequest,
    AuditLogItem,
    ResponseTimeDataPoint,
    RescueOutcomesData,
    NGOInsightsData,
    OrganizationProfile,
    OrganizationProfileUpdate,
    DispatchSettings,
)
from app.schemas.rescue import RescueResponse
from app.api.routes.rescues import build_rescue_response
from app.services.dispatch_service import DispatchService
from app.services.rescue_service import RescueService
from app.services.notification_service import NotificationService

router = APIRouter()

def check_org_scope(current_user: User, case: RescueCase, allow_unassigned_case: bool = False):
    """Ensure NGO admin only accesses cases within their authorized organization.
    
    Fail-closed policy:
    - Super Admin and Municipal Admin have global access.
    - NGO Admin requires current_user.organization_id to exist and match case.organization_id.
    - If allow_unassigned_case is False (default for private dossiers and evidence), case.organization_id
      must exist and match current_user.organization_id. A null case.organization_id does NOT grant access.
    """
    if current_user.role in [UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
        return

    if current_user.role == UserRole.NGO_ADMIN:
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: NGO Admin is not associated with an organization"
            )
        if case.organization_id:
            if case.organization_id != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Case belongs to another organization"
                )
        else:
            if not allow_unassigned_case:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Case belongs to another organization"
                )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: Insufficient privileges"
    )

def get_case_status_history_map(db: Session, case_ids: List[uuid.UUID]) -> Dict[uuid.UUID, Dict[RescueStatus, datetime]]:
    """Batch retrieves earliest status transition timestamp for a list of cases."""
    if not case_ids:
        return {}
    histories = (
        db.query(RescueStatusHistory)
        .filter(RescueStatusHistory.rescue_case_id.in_(case_ids))
        .order_by(RescueStatusHistory.created_at.asc())
        .all()
    )
    result: Dict[uuid.UUID, Dict[RescueStatus, datetime]] = {}
    for h in histories:
        if h.rescue_case_id not in result:
            result[h.rescue_case_id] = {}
        if h.new_status not in result[h.rescue_case_id]:
            result[h.rescue_case_id][h.new_status] = h.created_at
    return result

@router.get("/analytics/overview", response_model=NGOOverviewKPIs)
def get_ngo_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Retrieve operational KPIs calculated strictly from live rescue database data."""
    case_query = db.query(RescueCase)
    if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
        case_query = case_query.filter(
            (RescueCase.organization_id == current_user.organization_id) | (RescueCase.organization_id.is_(None))
        )
    all_cases = case_query.all()
    total_cases = len(all_cases)

    active_statuses = [
        s for s in RescueStatus if s not in [RescueStatus.CLOSED, RescueStatus.CANCELLED]
    ]
    active_cases = [c for c in all_cases if c.status in active_statuses]

    critical_count = sum(1 for c in active_cases if c.triage_priority == RescuePriority.CRITICAL)
    urgent_count = sum(1 for c in active_cases if c.triage_priority == RescuePriority.URGENT)
    searching_resp = sum(1 for c in active_cases if c.status == RescueStatus.SEARCHING_RESPONDER)
    awaiting_resp = sum(
        1 for c in active_cases if c.status in [RescueStatus.TRIAGED, RescueStatus.SEARCHING_RESPONDER]
    )
    en_route = sum(
        1 for c in active_cases if c.status in [RescueStatus.RESPONDER_ASSIGNED, RescueStatus.RESPONDER_EN_ROUTE]
    )
    under_treat = sum(1 for c in active_cases if c.status == RescueStatus.UNDER_TREATMENT)
    recovering = sum(1 for c in active_cases if c.status == RescueStatus.RECOVERING)
    unresolved_count = sum(1 for c in all_cases if c.status == RescueStatus.UNRESOLVED)

    # Cases closed today (UTC)
    now_utc = datetime.utcnow()
    start_of_today = datetime(now_utc.year, now_utc.month, now_utc.day)
    closed_today = sum(1 for c in all_cases if c.status == RescueStatus.CLOSED and c.closed_at and c.closed_at >= start_of_today)

    closed_cases = sum(1 for c in all_cases if c.status == RescueStatus.CLOSED)
    non_cancelled = sum(1 for c in all_cases if c.status != RescueStatus.CANCELLED)
    completion_rate = round((closed_cases / non_cancelled * 100.0) if non_cancelled > 0 else 0.0, 1)

    # Responders statistics (scoped if NGO admin)
    rescuer_query = db.query(User, RescuerProfile).join(RescuerProfile, RescuerProfile.user_id == User.id).filter(User.is_active == True)
    if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
        rescuer_query = rescuer_query.filter(
            (User.organization_id == current_user.organization_id) | (RescuerProfile.organization_id == current_user.organization_id)
        )
    rescuers = rescuer_query.all()
    total_rescuers = len(rescuers)
    available_rescuers = sum(1 for _, p in rescuers if p.availability_status == RescuerAvailability.AVAILABLE)
    assigned_rescuers = sum(1 for _, p in rescuers if p.availability_status == RescuerAvailability.BUSY)
    availability_pct = round((available_rescuers / total_rescuers * 100.0) if total_rescuers > 0 else 0.0, 1)

    # Distinct Operational Timings
    case_ids = [c.id for c in all_cases]
    dispatch_latencies_sec = []
    acceptance_latencies_sec = []
    arrival_times_min = []
    rescue_durations_min = []
    completion_times_min = []

    if case_ids:
        status_map = get_case_status_history_map(db, case_ids)
        assignments = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.rescue_case_id.in_(case_ids),
                RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED,
                RescueAssignment.accepted_at.isnot(None)
            )
            .all()
        )
        for a in assignments:
            start_time = a.offered_at or a.assigned_at
            if a.accepted_at and start_time:
                acc_diff = (a.accepted_at - start_time).total_seconds()
                if acc_diff >= 0:
                    acceptance_latencies_sec.append(acc_diff)

            # Arrival time from RescueStatusHistory (ANIMAL_LOCATED - accepted_at)
            # Strictly measures responder transit to arrival; excludes cases without arrival events
            hist = status_map.get(a.rescue_case_id, {})
            if RescueStatus.ANIMAL_LOCATED in hist and a.accepted_at:
                arr_diff = (hist[RescueStatus.ANIMAL_LOCATED] - a.accepted_at).total_seconds() / 60.0
                if arr_diff >= 0:
                    arrival_times_min.append(arr_diff)

        # Dispatch latency (first offer - reported) & rescue durations
        first_offers = (
            db.query(
                RescueAssignment.rescue_case_id,
                func.min(RescueAssignment.offered_at).label("first_offered_at")
            )
            .filter(RescueAssignment.rescue_case_id.in_(case_ids), RescueAssignment.offered_at.isnot(None))
            .group_by(RescueAssignment.rescue_case_id)
            .all()
        )
        offer_map = {row[0]: row[1] for row in first_offers}

        for c in all_cases:
            if c.id in offer_map and c.created_at and offer_map[c.id]:
                disp_diff = (offer_map[c.id] - c.created_at).total_seconds()
                if disp_diff >= 0:
                    dispatch_latencies_sec.append(disp_diff)

            hist = status_map.get(c.id, {})
            if RescueStatus.RESCUED in hist and c.created_at:
                resc_diff = (hist[RescueStatus.RESCUED] - c.created_at).total_seconds() / 60.0
                if resc_diff >= 0:
                    rescue_durations_min.append(resc_diff)

            if c.status == RescueStatus.CLOSED and c.closed_at and c.created_at:
                comp_diff = (c.closed_at - c.created_at).total_seconds() / 60.0
                if comp_diff >= 0:
                    completion_times_min.append(comp_diff)

    avg_dispatch = round(sum(dispatch_latencies_sec) / len(dispatch_latencies_sec), 1) if dispatch_latencies_sec else None
    avg_acceptance_sec = round(sum(acceptance_latencies_sec) / len(acceptance_latencies_sec), 1) if acceptance_latencies_sec else None
    avg_arrival = round(sum(arrival_times_min) / len(arrival_times_min), 1) if arrival_times_min else None
    avg_completion = round(sum(completion_times_min) / len(completion_times_min), 1) if completion_times_min else 0.0
    avg_rescue = round(sum(rescue_durations_min) / len(rescue_durations_min), 1) if rescue_durations_min else None

    return NGOOverviewKPIs(
        active_cases=len(active_cases),
        critical_cases=critical_count,
        urgent_cases=urgent_count,
        searching_responder_cases=searching_resp,
        awaiting_responder=awaiting_resp,
        responders_en_route=en_route,
        responders_available=available_rescuers,
        responders_assigned=assigned_rescuers,
        under_treatment=under_treat,
        recovering=recovering,
        unresolved_cases=unresolved_count,
        closed_today=closed_today,
        avg_dispatch_seconds=avg_dispatch or 0.0,
        average_response_minutes=avg_arrival,
        avg_completion_minutes=avg_completion,
        completion_rate_pct=completion_rate,
        responder_availability_pct=availability_pct,
        total_cases=total_cases,
        average_dispatch_latency_seconds=avg_dispatch,
        average_acceptance_latency_seconds=avg_acceptance_sec,
        average_arrival_minutes=avg_arrival,
        average_rescue_duration_minutes=avg_rescue,
        average_case_completion_minutes=avg_completion,
    )

@router.get("/analytics/response-times", response_model=List[ResponseTimeDataPoint])
def get_response_time_analytics(
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Real response time trend dataset calculated from case assignments over period."""
    days = 7 if period == "7d" else (90 if period == "90d" else 30)
    cutoff = datetime.utcnow() - timedelta(days=days)

    case_query = db.query(RescueCase).filter(RescueCase.created_at >= cutoff)
    if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
        case_query = case_query.filter(
            (RescueCase.organization_id == current_user.organization_id) | (RescueCase.organization_id.is_(None))
        )
    cases = case_query.all()
    case_ids = [c.id for c in cases]
    status_map = get_case_status_history_map(db, case_ids)

    daily_stats: Dict[str, Dict[str, Any]] = {}
    for i in range(days):
        d_str = (cutoff + timedelta(days=i+1)).strftime("%Y-%m-%d")
        daily_stats[d_str] = {"total_minutes": 0.0, "cases": 0}

    if case_ids:
        assignments = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.rescue_case_id.in_(case_ids),
                RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED,
                RescueAssignment.accepted_at.isnot(None),
            )
            .all()
        )
        for a in assignments:
            if a.accepted_at:
                date_key = a.accepted_at.strftime("%Y-%m-%d")
                hist = status_map.get(a.rescue_case_id, {})
                if RescueStatus.ANIMAL_LOCATED in hist:
                    diff_min = max(0.0, (hist[RescueStatus.ANIMAL_LOCATED] - a.accepted_at).total_seconds() / 60.0)
                    if date_key in daily_stats:
                        daily_stats[date_key]["total_minutes"] += diff_min
                        daily_stats[date_key]["cases"] += 1
                    else:
                        daily_stats[date_key] = {"total_minutes": diff_min, "cases": 1}

    results = []
    for d_str in sorted(daily_stats.keys()):
        item = daily_stats[d_str]
        avg_m = round(item["total_minutes"] / item["cases"], 1) if item["cases"] > 0 else None
        results.append(ResponseTimeDataPoint(
            date=d_str,
            average_response_minutes=avg_m,
            cases=item["cases"]
        ))

    return results

@router.get("/analytics/outcomes", response_model=RescueOutcomesData)
def get_rescue_outcomes(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Aggregate rescue terminal & current outcomes with correct categorization and success rates."""
    case_query = db.query(RescueCase)
    if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
        case_query = case_query.filter(
            (RescueCase.organization_id == current_user.organization_id) | (RescueCase.organization_id.is_(None))
        )
    cases = case_query.all()
    total_cases = len(cases)

    outcomes = {
        "RESCUED": 0,
        "UNDER_TREATMENT": 0,
        "RECOVERING": 0,
        "RELEASED": 0,
        "ADOPTED": 0,
        "CLOSED": 0,
        "UNRESOLVED": 0,
    }

    active_field = 0
    rescued_transport = 0
    medical_care = 0
    post_care = 0
    successful_terminal = 0
    failure_exception = 0

    for c in cases:
        status_val = c.status.value
        if status_val in outcomes:
            outcomes[status_val] += 1

        # Categorization
        if c.status in [
            RescueStatus.REPORTED,
            RescueStatus.TRIAGED,
            RescueStatus.SEARCHING_RESPONDER,
            RescueStatus.RESPONDER_ASSIGNED,
            RescueStatus.RESPONDER_EN_ROUTE,
            RescueStatus.ANIMAL_LOCATED,
        ]:
            active_field += 1
        elif c.status in [
            RescueStatus.RESCUED,
            RescueStatus.TRANSPORTING,
            RescueStatus.AT_VETERINARY_FACILITY,
        ]:
            rescued_transport += 1
        elif c.status in [
            RescueStatus.UNDER_TREATMENT,
            RescueStatus.RECOVERING,
        ]:
            medical_care += 1
        elif c.status in [
            RescueStatus.FOSTER_CARE,
            RescueStatus.READY_FOR_RELEASE,
            RescueStatus.READY_FOR_ADOPTION,
        ]:
            post_care += 1
        elif c.status in [
            RescueStatus.RELEASED,
            RescueStatus.ADOPTED,
            RescueStatus.CLOSED,
        ]:
            successful_terminal += 1
        elif c.status in [
            RescueStatus.UNRESOLVED,
            RescueStatus.CANCELLED,
        ]:
            failure_exception += 1

    # Correct success rate: strictly terminal successful outcomes
    success_rate = round((successful_terminal / total_cases * 100.0) if total_cases > 0 else 0.0, 1)
    unresolved_rate = round((outcomes["UNRESOLVED"] / total_cases * 100.0) if total_cases > 0 else 0.0, 1)

    vet_handoff_count = sum(
        1 for c in cases
        if c.veterinary_facility_id is not None or c.status in [
            RescueStatus.AT_VETERINARY_FACILITY,
            RescueStatus.UNDER_TREATMENT,
            RescueStatus.RECOVERING,
            RescueStatus.READY_FOR_RELEASE,
            RescueStatus.RELEASED,
        ]
    )
    vet_handoff_rate = round((vet_handoff_count / total_cases * 100.0) if total_cases > 0 else 0.0, 1)

    return RescueOutcomesData(
        outcomes=outcomes,
        rescue_success_rate=success_rate,
        unresolved_rate=unresolved_rate,
        veterinary_handoff_rate=vet_handoff_rate,
        total_cases=total_cases,
        active_field_count=active_field,
        rescued_transport_count=rescued_transport,
        medical_care_count=medical_care,
        post_care_count=post_care,
        successful_terminal_count=successful_terminal,
        failure_exception_count=failure_exception,
        failure_count=failure_exception,
    )

@router.get("/analytics/hotspots", response_model=List[HotspotItem])
def get_incident_hotspots(
    period: str = Query("30d", pattern="^(7d|30d|90d)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Return tenant-isolated aggregated rescue incident clusters with real response measurements and date range filtering."""
    days = 7 if period == "7d" else (90 if period == "90d" else 30)
    cutoff = datetime.utcnow() - timedelta(days=days)

    case_query = db.query(RescueCase).filter(RescueCase.created_at >= cutoff)
    if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
        case_query = case_query.filter(
            (RescueCase.organization_id == current_user.organization_id) | (RescueCase.organization_id.is_(None))
        )

    dialect_name = db.bind.dialect.name if db.bind else "sqlite"
    if dialect_name == "postgresql":
        # PostGIS ST_SnapToGrid for spatial grouping
        grid_cases = (
            case_query.with_entities(
                RescueCase,
                func.ST_Y(func.ST_SnapToGrid(func.ST_SetSRID(func.ST_MakePoint(RescueCase.longitude, RescueCase.latitude), 4326), 0.01)).label("grid_lat"),
                func.ST_X(func.ST_SnapToGrid(func.ST_SetSRID(func.ST_MakePoint(RescueCase.longitude, RescueCase.latitude), 4326), 0.01)).label("grid_lng"),
            ).all()
        )
        cases_with_coords = [(row[0], float(row[1]) if row[1] is not None else round(row[0].latitude, 2), float(row[2]) if row[2] is not None else round(row[0].longitude, 2)) for row in grid_cases]
    else:
        cases = case_query.all()
        cases_with_coords = [(c, round(c.latitude, 2), round(c.longitude, 2)) for c in cases]

    case_ids = [item[0].id for item in cases_with_coords]
    status_map = get_case_status_history_map(db, case_ids)

    assignments = (
        db.query(RescueAssignment)
        .filter(
            RescueAssignment.rescue_case_id.in_(case_ids),
            RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED,
            RescueAssignment.accepted_at.isnot(None),
        )
        .all()
    ) if case_ids else []
    assignment_map = {a.rescue_case_id: a for a in assignments}

    clusters: Dict[tuple, Dict[str, Any]] = {}

    for c, grid_lat, grid_lng in cases_with_coords:
        key = (grid_lat, grid_lng)

        if key not in clusters:
            clusters[key] = {
                "latitude": grid_lat,
                "longitude": grid_lng,
                "area_name": c.address_text or f"Coordinates ({grid_lat}, {grid_lng})",
                "incident_count": 0,
                "critical_count": 0,
                "urgent_count": 0,
                "species_count": {},
                "acceptance_times": [],
                "arrival_times": [],
            }
        clusters[key]["incident_count"] += 1
        if c.triage_priority == RescuePriority.CRITICAL:
            clusters[key]["critical_count"] += 1
        elif c.triage_priority == RescuePriority.URGENT:
            clusters[key]["urgent_count"] += 1
        sp = c.species or "Canine"
        clusters[key]["species_count"][sp] = clusters[key]["species_count"].get(sp, 0) + 1

        assign = assignment_map.get(c.id)
        if assign and assign.accepted_at and (assign.offered_at or assign.assigned_at):
            start = assign.offered_at or assign.assigned_at
            acc_diff = max(0.0, (assign.accepted_at - start).total_seconds() / 60.0)
            clusters[key]["acceptance_times"].append(acc_diff)

        hist = status_map.get(c.id, {})
        if RescueStatus.ANIMAL_LOCATED in hist and assign and assign.accepted_at:
            arr_diff = max(0.0, (hist[RescueStatus.ANIMAL_LOCATED] - assign.accepted_at).total_seconds() / 60.0)
            clusters[key]["arrival_times"].append(arr_diff)

    results = []
    for data in clusters.values():
        top_sp = max(data["species_count"].items(), key=lambda x: x[1])[0] if data["species_count"] else "Canine"
        avg_acc = round(sum(data["acceptance_times"]) / len(data["acceptance_times"]), 1) if data["acceptance_times"] else None
        avg_arr = round(sum(data["arrival_times"]) / len(data["arrival_times"]), 1) if data["arrival_times"] else None

        results.append(
            HotspotItem(
                latitude=data["latitude"],
                longitude=data["longitude"],
                area_name=data["area_name"],
                incident_count=data["incident_count"],
                critical_count=data["critical_count"],
                urgent_count=data["urgent_count"],
                top_species=top_sp,
                average_response_minutes=avg_arr,
                average_acceptance_minutes=avg_acc,
                average_arrival_minutes=avg_arr,
            )
        )

    results.sort(key=lambda x: -x.incident_count)
    return results[:50]

@router.get("/analytics/insights", response_model=NGOInsightsData)
def get_ngo_operational_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Operational heuristics: busiest days, top areas, acceptance rates, and radius escalations."""
    case_query = db.query(RescueCase)
    if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
        case_query = case_query.filter(
            (RescueCase.organization_id == current_user.organization_id) | (RescueCase.organization_id.is_(None))
        )
    cases = case_query.all()
    case_ids = [c.id for c in cases]

    if not cases:
        return NGOInsightsData()

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_counts = {d: 0 for d in days}
    for c in cases:
        if c.created_at:
            day_counts[days[c.created_at.weekday()]] += 1
    busiest_day = max(day_counts.items(), key=lambda x: x[1])[0] if any(day_counts.values()) else None

    hour_windows = {
        "00:00 - 04:00": 0,
        "04:00 - 08:00": 0,
        "08:00 - 12:00": 0,
        "12:00 - 16:00": 0,
        "16:00 - 20:00": 0,
        "20:00 - 24:00": 0,
    }
    for c in cases:
        if c.created_at:
            h = c.created_at.hour
            if 0 <= h < 4: hour_windows["00:00 - 04:00"] += 1
            elif 4 <= h < 8: hour_windows["04:00 - 08:00"] += 1
            elif 8 <= h < 12: hour_windows["08:00 - 12:00"] += 1
            elif 12 <= h < 16: hour_windows["12:00 - 16:00"] += 1
            elif 16 <= h < 20: hour_windows["16:00 - 20:00"] += 1
            else: hour_windows["20:00 - 24:00"] += 1
    busiest_time = max(hour_windows.items(), key=lambda x: x[1])[0] if any(hour_windows.values()) else None

    area_counts: Dict[str, int] = {}
    for c in cases:
        loc = c.address_text or "Central Operational Zone"
        area_counts[loc] = area_counts.get(loc, 0) + 1
    top_area = max(area_counts.items(), key=lambda x: x[1])[0] if area_counts else None

    total_offers = 0
    accepted_offers = 0
    escalated_cases = 0
    total_attempts = 0

    if case_ids:
        all_assignments = db.query(RescueAssignment).filter(RescueAssignment.rescue_case_id.in_(case_ids)).all()
        total_offers = len(all_assignments)
        accepted_offers = sum(1 for a in all_assignments if a.assignment_status == AssignmentStatus.ACCEPTED)

    for c in cases:
        attempts = c.dispatch_attempt or 1
        total_attempts += attempts
        if attempts > 1 or (c.dispatch_radius_km and c.dispatch_radius_km > 5.0):
            escalated_cases += 1

    acc_rate = round((accepted_offers / total_offers * 100.0) if total_offers > 0 else 0.0, 1)
    avg_attempts = round((total_attempts / len(cases)) if cases else 1.0, 1)
    esc_rate = round((escalated_cases / len(cases) * 100.0) if cases else 0.0, 1)

    return NGOInsightsData(
        busiest_day=busiest_day,
        busiest_time_range=busiest_time,
        top_rescue_area=top_area,
        responder_acceptance_rate_pct=acc_rate,
        avg_dispatch_attempts=avg_attempts,
        escalation_rate_pct=esc_rate,
    )

@router.get("/cases", response_model=List[RescueResponse])
def get_ngo_cases(
    priority: Optional[RescuePriority] = None,
    status: Optional[RescueStatus] = None,
    species: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Retrieve filtered and searchable rescue cases for NGO case management."""
    query = db.query(RescueCase)
    if current_user.role == UserRole.NGO_ADMIN:
        # Discovery policy: NGO admins can discover cases belonging to their own organization
        # as well as unassigned cases available for response/intake. Cross-tenant cases are strictly excluded.
        if current_user.organization_id:
            query = query.filter(
                (RescueCase.organization_id == current_user.organization_id) | (RescueCase.organization_id.is_(None))
            )
        else:
            query = query.filter(RescueCase.organization_id.is_(None))

    if priority:
        query = query.filter(RescueCase.triage_priority == priority)
    if status:
        query = query.filter(RescueCase.status == status)
    if species:
        query = query.filter(RescueCase.species.ilike(f"%{species}%"))
    if search:
        s = f"%{search}%"
        query = query.filter(
            (RescueCase.case_number.ilike(s)) |
            (RescueCase.description.ilike(s)) |
            (RescueCase.address_text.ilike(s)) |
            (RescueCase.species.ilike(s))
        )

    cases = query.order_by(RescueCase.created_at.desc()).offset(skip).limit(limit).all()
    return [build_rescue_response(c, include_evidence=True, presign_images=False) for c in cases]

@router.get("/cases/{case_id}")
def get_ngo_case_dossier(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Complete dossier for a single case including timeline, offers, and audit logs."""
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Rescue case not found")

    check_org_scope(current_user, case)

    resp = build_rescue_response(case, include_evidence=True, presign_images=False).model_dump()

    # Add assignment offers history
    assignments = (
        db.query(RescueAssignment)
        .filter(RescueAssignment.rescue_case_id == case_id)
        .order_by(RescueAssignment.offered_at.desc())
        .all()
    )
    offers_data = []
    for a in assignments:
        rescuer_name = a.rescuer.full_name if a.rescuer else "Unknown"
        offers_data.append({
            "id": str(a.id),
            "rescuer_id": str(a.rescuer_id),
            "rescuer_name": rescuer_name,
            "status": a.assignment_status.value,
            "distance_km": a.distance_km,
            "dispatch_score": a.dispatch_score,
            "offered_at": a.offered_at.isoformat() if a.offered_at else None,
            "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            "expired_at": a.expired_at.isoformat() if a.expired_at else None,
            "accepted_at": a.accepted_at.isoformat() if a.accepted_at else None,
            "rejected_at": a.rejected_at.isoformat() if a.rejected_at else None,
            "rejection_reason": a.rejection_reason,
        })
    resp["dispatch_offers"] = offers_data
    resp["dispatch_progression"] = {
        "attempt": case.dispatch_attempt or 1,
        "radius_km": case.dispatch_radius_km or 5.0,
        "last_dispatch_at": case.last_dispatch_at.isoformat() if case.last_dispatch_at else None,
    }

    # Add audit logs
    audit_logs = (
        db.query(AuditLog)
        .filter(AuditLog.entity == "rescue_case", AuditLog.entity_id == case_id)
        .order_by(AuditLog.timestamp.desc())
        .all()
    )
    resp["audit_trail"] = [
        {
            "id": str(log.id),
            "actor_id": str(log.actor_id) if log.actor_id else None,
            "action": log.action,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in audit_logs
    ]

    return resp

@router.post("/cases/{case_id}/actions")
@router.post("/cases/{case_id}/action")
def execute_ngo_case_action(
    case_id: uuid.UUID,
    payload: NGOCaseActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Privileged administrative actions on a rescue case with audit logging."""
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Rescue case not found")

    check_org_scope(current_user, case, allow_unassigned_case=True)

    # Claim unassigned case to current NGO organization if applicable
    if not case.organization_id and current_user.organization_id:
        case.organization_id = current_user.organization_id

    old_status = case.status.value
    action_type = payload.action.lower()

    if action_type == "re_dispatch":
        # Cancel old pending offers
        db.query(RescueAssignment).filter(
            RescueAssignment.rescue_case_id == case.id,
            RescueAssignment.assignment_status == AssignmentStatus.PENDING
        ).update({"assignment_status": AssignmentStatus.CANCELLED}, synchronize_session=False)

        case.status = RescueStatus.SEARCHING_RESPONDER
        db.commit()

        # Audit log
        audit = AuditLog(
            actor_id=current_user.id,
            action="RE_DISPATCH",
            entity="rescue_case",
            entity_id=case.id,
            old_value={"status": old_status},
            new_value={"status": RescueStatus.SEARCHING_RESPONDER.value, "reason": payload.reason},
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        db.commit()

        # Trigger dispatch
        DispatchService.dispatch_case(db, case.id)
        return {"success": True, "message": f"Case {case.case_number} redispatch triggered"}

    elif action_type == "cancel":
        RescueService.update_status(
            db=db,
            rescue_case=case,
            new_status=RescueStatus.CANCELLED,
            user_id=current_user.id,
            notes=payload.reason or "Administrative cancellation by NGO Admin"
        )
        audit = AuditLog(
            actor_id=current_user.id,
            action="ADMIN_CANCEL",
            entity="rescue_case",
            entity_id=case.id,
            old_value={"status": old_status},
            new_value={"status": RescueStatus.CANCELLED.value, "reason": payload.reason},
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        db.commit()
        return {"success": True, "message": "Case cancelled"}

    elif action_type == "mark_unresolved":
        RescueService.update_status(
            db=db,
            rescue_case=case,
            new_status=RescueStatus.UNRESOLVED,
            user_id=current_user.id,
            notes=payload.reason or "Marked unresolved by NGO Admin"
        )
        audit = AuditLog(
            actor_id=current_user.id,
            action="MARK_UNRESOLVED",
            entity="rescue_case",
            entity_id=case.id,
            old_value={"status": old_status},
            new_value={"status": RescueStatus.UNRESOLVED.value, "reason": payload.reason},
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        db.commit()
        return {"success": True, "message": "Case marked unresolved"}

    elif action_type == "assign_responder":
        if not payload.rescuer_id:
            raise HTTPException(status_code=400, detail="rescuer_id is required for manual assignment")
        rescuer = db.query(User).filter(User.id == payload.rescuer_id, User.role == UserRole.RESCUER).first()
        if not rescuer:
            raise HTTPException(status_code=404, detail="Rescuer not found")

        # Tenant check: NGO Admin can only assign rescuers belonging to their organization
        if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
            rescuer_profile = db.query(RescuerProfile).filter(RescuerProfile.user_id == rescuer.id).first()
            rescuer_org = rescuer.organization_id or (rescuer_profile.organization_id if rescuer_profile else None)
            if rescuer_org and rescuer_org != current_user.organization_id:
                audit = AuditLog(
                    actor_id=current_user.id,
                    action="CROSS_TENANT_RESPONDER_ASSIGNMENT_DENIED",
                    entity="rescue_case",
                    entity_id=case.id,
                    old_value={"status": old_status},
                    new_value={"target_rescuer_id": str(rescuer.id), "target_org_id": str(rescuer_org)},
                    timestamp=datetime.utcnow()
                )
                db.add(audit)
                db.commit()
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign responder from another organization")

        # Create accepted assignment
        assignment = RescueAssignment(
            rescue_case_id=case.id,
            rescuer_id=rescuer.id,
            assigned_at=datetime.utcnow(),
            accepted_at=datetime.utcnow(),
            assignment_status=AssignmentStatus.ACCEPTED,
        )
        db.add(assignment)

        # Cancel others
        db.query(RescueAssignment).filter(
            RescueAssignment.rescue_case_id == case.id,
            RescueAssignment.rescuer_id != rescuer.id,
            RescueAssignment.assignment_status == AssignmentStatus.PENDING
        ).update({"assignment_status": AssignmentStatus.CANCELLED}, synchronize_session=False)

        RescueService.update_status(
            db=db,
            rescue_case=case,
            new_status=RescueStatus.RESPONDER_ASSIGNED,
            user_id=current_user.id,
            notes=f"Manually assigned by NGO Admin: {rescuer.full_name}"
        )

        audit = AuditLog(
            actor_id=current_user.id,
            action="MANUAL_ASSIGNMENT",
            entity="rescue_case",
            entity_id=case.id,
            old_value={"status": old_status},
            new_value={"status": RescueStatus.RESPONDER_ASSIGNED.value, "rescuer_id": str(rescuer.id)},
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        db.commit()

        # Notify rescuer
        NotificationService.notify_user(
            db=db,
            user_id=rescuer.id,
            title="Assigned to Rescue Case",
            message=f"You have been manually assigned to case {case.case_number} by an NGO admin.",
            notification_type="RESPONDER_ASSIGNED",
            rescue_case_id=case.id,
        )
        return {"success": True, "message": f"Case assigned to {rescuer.full_name}"}

    elif action_type == "change_facility":
        if not payload.veterinary_facility_id:
            raise HTTPException(status_code=400, detail="veterinary_facility_id is required")
        facility = db.query(VeterinaryFacility).filter(VeterinaryFacility.id == payload.veterinary_facility_id).first()
        if not facility:
            raise HTTPException(status_code=404, detail="Veterinary facility not found")

        # Tenant check: NGO Admin can only assign facilities belonging to their organization or public/shared facilities
        if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
            if facility.organization_id is not None and facility.organization_id != current_user.organization_id:
                audit = AuditLog(
                    actor_id=current_user.id,
                    action="CROSS_TENANT_FACILITY_ASSIGNMENT_DENIED",
                    entity="rescue_case",
                    entity_id=case.id,
                    old_value={"status": old_status},
                    new_value={"target_facility_id": str(facility.id), "facility_org_id": str(facility.organization_id)},
                    timestamp=datetime.utcnow()
                )
                db.add(audit)
                db.commit()
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign private veterinary facility of another organization")

        old_fac_id = str(case.veterinary_facility_id) if case.veterinary_facility_id else None
        case.veterinary_facility_id = facility.id
        db.commit()

        audit = AuditLog(
            actor_id=current_user.id,
            action="CHANGE_FACILITY",
            entity="rescue_case",
            entity_id=case.id,
            old_value={"veterinary_facility_id": old_fac_id},
            new_value={"veterinary_facility_id": str(facility.id), "facility_name": facility.name},
            timestamp=datetime.utcnow()
        )
        db.add(audit)
        db.commit()
        return {"success": True, "message": f"Destination facility updated to {facility.name}"}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown administrative action: {payload.action}")

@router.get("/responders", response_model=List[NGOResponderSummary])
def get_ngo_responders(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Roster of rescue responders with availability, fleet metrics, and performance indicators."""
    query = (
        db.query(User, RescuerProfile)
        .join(RescuerProfile, RescuerProfile.user_id == User.id)
        .filter(User.role == UserRole.RESCUER)
    )
    if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
        query = query.filter(
            (User.organization_id == current_user.organization_id) | (RescuerProfile.organization_id == current_user.organization_id)
        )

    records = query.all()
    results = []

    for user, profile in records:
        # Completed rescues
        completed = (
            db.query(RescueAssignment)
            .join(RescueCase, RescueCase.id == RescueAssignment.rescue_case_id)
            .filter(
                RescueAssignment.rescuer_id == user.id,
                RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED,
                RescueCase.status.in_([RescueStatus.CLOSED, RescueStatus.READY_FOR_RELEASE, RescueStatus.RELEASED])
            )
            .count()
        )
        # Offers metrics
        all_offers = (
            db.query(RescueAssignment)
            .filter(RescueAssignment.rescuer_id == user.id)
            .all()
        )
        total_offers = len(all_offers)
        accepted_offers = sum(1 for a in all_offers if a.assignment_status == AssignmentStatus.ACCEPTED)
        acc_rate = round((accepted_offers / total_offers * 100.0) if total_offers > 0 else 100.0, 1)

        # Active mission
        active_assignment = (
            db.query(RescueAssignment)
            .join(RescueCase, RescueCase.id == RescueAssignment.rescue_case_id)
            .filter(
                RescueAssignment.rescuer_id == user.id,
                RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED,
                RescueCase.status.notin_([RescueStatus.CLOSED, RescueStatus.CANCELLED])
            )
            .first()
        )
        active_case_num = active_assignment.rescue_case.case_number if active_assignment and active_assignment.rescue_case else None

        results.append(
            NGOResponderSummary(
                id=profile.id,
                user_id=user.id,
                full_name=user.full_name,
                phone=user.phone,
                email=user.email,
                is_active=user.is_active,
                availability_status=profile.availability_status,
                latitude=profile.latitude,
                longitude=profile.longitude,
                last_location_update=profile.last_location_update,
                vehicle_available=profile.vehicle_available,
                experience_level=profile.experience_level or "Intermediate",
                reliability_score=profile.reliability_score or 100.0,
                completed_rescues=completed,
                total_offers=total_offers,
                accepted_offers=accepted_offers,
                acceptance_rate_pct=acc_rate,
                active_case_number=active_case_num,
            )
        )

    results.sort(key=lambda r: (-r.completed_rescues, r.full_name))
    return results

@router.patch("/responders/{user_id}/status")
def update_responder_status(
    user_id: uuid.UUID,
    payload: NGOResponderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Toggle responder active status or update operational affiliation with audit trail."""
    user = db.query(User).filter(User.id == user_id, User.role == UserRole.RESCUER).first()
    if not user:
        raise HTTPException(status_code=404, detail="Responder not found")

    profile = db.query(RescuerProfile).filter(RescuerProfile.user_id == user.id).first()
    responder_org = user.organization_id or (profile.organization_id if profile else None)

    # Cross-tenant boundary check: NGO_ADMIN can only modify responders belonging to their organization
    if current_user.role == UserRole.NGO_ADMIN:
        attempted = payload.model_dump(mode="json", exclude_unset=True)

        # Block NGO admin from adopting or reassigning responder organization_id
        if payload.organization_id is not None and payload.organization_id != responder_org:
            audit = AuditLog(
                actor_id=current_user.id,
                action="CROSS_TENANT_RESPONDER_UPDATE_DENIED",
                entity="user",
                entity_id=user.id,
                old_value={"organization_id": str(responder_org) if responder_org else None},
                new_value={
                    "actor_organization_id": str(current_user.organization_id) if current_user.organization_id else None,
                    "target_responder_id": str(user.id),
                    "target_organization_id": str(responder_org) if responder_org else None,
                    "attempted_target_org": str(payload.organization_id),
                },
                timestamp=datetime.utcnow()
            )
            db.add(audit)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization reassignment is restricted to super administrators"
            )

        if not current_user.organization_id or responder_org != current_user.organization_id:
            audit = AuditLog(
                actor_id=current_user.id,
                action="CROSS_TENANT_RESPONDER_UPDATE_DENIED",
                entity="user",
                entity_id=user.id,
                old_value={"organization_id": str(responder_org) if responder_org else None},
                new_value={
                    "actor_organization_id": str(current_user.organization_id) if current_user.organization_id else None,
                    "target_responder_id": str(user.id),
                    "target_organization_id": str(responder_org) if responder_org else None,
                    "attempted_fields": attempted,
                },
                timestamp=datetime.utcnow()
            )
            db.add(audit)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Responder belongs to another organization or is unaffiliated"
            )

    old_val = {"is_active": user.is_active, "organization_id": str(user.organization_id) if user.organization_id else None}
    new_val = {}

    if payload.is_active is not None:
        user.is_active = payload.is_active
        new_val["is_active"] = payload.is_active

    if payload.organization_id is not None:
        # Permitted for SUPER_ADMIN
        user.organization_id = payload.organization_id
        if profile:
            profile.organization_id = payload.organization_id
        new_val["organization_id"] = str(payload.organization_id)

    if payload.reliability_score is not None and profile:
        profile.reliability_score = payload.reliability_score
        new_val["reliability_score"] = payload.reliability_score

    audit = AuditLog(
        actor_id=current_user.id,
        action="UPDATE_RESPONDER_STATUS",
        entity="user",
        entity_id=user.id,
        old_value=old_val,
        new_value=new_val,
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    db.commit()

    return {"success": True, "message": f"Updated responder {user.full_name}"}

@router.get("/veterinary")
def get_ngo_veterinary_network(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """List partner veterinary clinics with current patient intake metrics."""
    fac_query = db.query(VeterinaryFacility)
    if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
        fac_query = fac_query.filter(
            (VeterinaryFacility.organization_id == current_user.organization_id) | (VeterinaryFacility.organization_id.is_(None))
        )
    facilities = fac_query.all()
    results = []
    for f in facilities:
        admitted = (
            db.query(RescueCase)
            .filter(
                RescueCase.veterinary_facility_id == f.id,
                RescueCase.status.in_([
                    RescueStatus.AT_VETERINARY_FACILITY,
                    RescueStatus.UNDER_TREATMENT,
                    RescueStatus.RECOVERING
                ])
            )
            .count()
        )
        results.append({
            "id": str(f.id),
            "name": f.name,
            "address": f.address,
            "phone": f.phone,
            "email": f.email,
            "supports_emergency": f.supports_emergency,
            "is_24_hours": f.is_24_hours,
            "is_verified": f.is_verified,
            "latitude": f.latitude,
            "longitude": f.longitude,
            "current_admitted_patients": admitted,
        })
    return results

@router.get("/organization", response_model=OrganizationProfile)
def get_ngo_organization_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Retrieve organization profile, operational region, and team sizes."""
    org = None
    if current_user.organization_id:
        org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    elif current_user.role == UserRole.SUPER_ADMIN:
        org = db.query(Organization).first()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found for current user")

    responders_count = db.query(User).filter(User.organization_id == org.id, User.role == UserRole.RESCUER).count()
    facilities_count = db.query(VeterinaryFacility).filter(VeterinaryFacility.organization_id == org.id).count()

    return OrganizationProfile(
        id=org.id,
        name=org.name,
        organization_type=org.organization_type.value if hasattr(org.organization_type, "value") else str(org.organization_type),
        email=org.email,
        phone=org.phone,
        address=org.address,
        operating_region=getattr(org, "operating_region", None),
        description=getattr(org, "description", None),
        responders_count=responders_count,
        veterinary_partners_count=facilities_count,
        created_at=org.created_at,
        is_active=org.verification_status if org.verification_status is not None else True,
    )

@router.patch("/organization", response_model=OrganizationProfile)
def update_ngo_organization_profile(
    payload: OrganizationProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Update safe organization profile fields with audit trail. Tenant ownership cannot be hijacked."""
    if not current_user.organization_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="User is not associated with an organization")

    org = None
    if current_user.organization_id:
        org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    elif current_user.role == UserRole.SUPER_ADMIN:
        org = db.query(Organization).first()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    old_vals = {
        "name": org.name,
        "email": org.email,
        "phone": org.phone,
        "address": org.address,
        "operating_region": getattr(org, "operating_region", None),
        "description": getattr(org, "description", None),
    }

    if payload.name is not None and payload.name.strip():
        org.name = payload.name.strip()
    if payload.email is not None:
        org.email = payload.email.strip()
    if payload.phone is not None:
        org.phone = payload.phone.strip()
    if payload.address is not None:
        org.address = payload.address.strip()
    if payload.operating_region is not None:
        org.operating_region = payload.operating_region.strip()
    if payload.description is not None:
        org.description = payload.description.strip()

    audit = AuditLog(
        actor_id=current_user.id,
        action="UPDATE_ORGANIZATION_PROFILE",
        entity="organization",
        entity_id=org.id,
        old_value=old_vals,
        new_value={k: getattr(org, k, None) for k in old_vals.keys()},
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    db.refresh(org)

    responders_count = db.query(User).filter(User.organization_id == org.id, User.role == UserRole.RESCUER).count()
    facilities_count = db.query(VeterinaryFacility).filter(VeterinaryFacility.organization_id == org.id).count()

    return OrganizationProfile(
        id=org.id,
        name=org.name,
        organization_type=org.organization_type.value if hasattr(org.organization_type, "value") else str(org.organization_type),
        email=org.email,
        phone=org.phone,
        address=org.address,
        operating_region=getattr(org, "operating_region", None),
        description=getattr(org, "description", None),
        responders_count=responders_count,
        veterinary_partners_count=facilities_count,
        created_at=org.created_at,
        is_active=org.verification_status if org.verification_status is not None else True,
    )

@router.get("/settings/dispatch", response_model=DispatchSettings)
def get_ngo_dispatch_settings(
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Retrieve operational dispatch parameters: radius escalation levels and timeouts."""
    raw_levels = settings.DISPATCH_RADIUS_LEVELS.split(",")
    levels = []
    for x in raw_levels:
        try:
            levels.append(float(x.strip()))
        except ValueError:
            pass

    return DispatchSettings(
        default_radius_km=levels[0] if levels else 5.0,
        radius_escalation_levels=levels or [5.0, 10.0, 20.0, 40.0],
        offer_expiration_seconds=settings.DISPATCH_OFFER_EXPIRY_SECONDS,
        stale_location_timeout_seconds=settings.RESPONDER_LOCATION_STALE_MINUTES * 60,
    )

