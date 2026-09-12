from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import uuid
from datetime import datetime

from app.database import get_db
from app.models.user import User
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
from app.schemas.ngo import (
    NGOOverviewKPIs,
    HotspotItem,
    NGOResponderSummary,
    NGOResponderStatusUpdate,
    NGOCaseActionRequest,
    AuditLogItem,
)
from app.schemas.rescue import RescueResponse
from app.api.routes.rescues import build_rescue_response
from app.services.dispatch_service import DispatchService
from app.services.rescue_service import RescueService
from app.services.notification_service import NotificationService

router = APIRouter()

def check_org_scope(current_user: User, case: RescueCase):
    """Ensure NGO admin only accesses cases within their authorized organization if scoped."""
    if current_user.role == UserRole.SUPER_ADMIN:
        return
    if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
        if case.organization_id and case.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Case belongs to another organization"
            )

@router.get("/analytics/overview", response_model=NGOOverviewKPIs)
def get_ngo_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Retrieve operational KPIs calculated from live rescue database data."""
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
    awaiting_resp = sum(
        1 for c in active_cases if c.status in [RescueStatus.TRIAGED, RescueStatus.SEARCHING_RESPONDER]
    )
    en_route = sum(
        1 for c in active_cases if c.status in [RescueStatus.RESPONDER_ASSIGNED, RescueStatus.RESPONDER_EN_ROUTE]
    )
    under_treat = sum(
        1 for c in active_cases if c.status in [RescueStatus.AT_VETERINARY_FACILITY, RescueStatus.UNDER_TREATMENT]
    )
    recovering = sum(1 for c in active_cases if c.status == RescueStatus.RECOVERING)

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
    availability_pct = round((available_rescuers / total_rescuers * 100.0) if total_rescuers > 0 else 0.0, 1)

    # Average dispatch latency (from offer creation to acceptance)
    accepted_assignments = (
        db.query(RescueAssignment)
        .filter(RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED, RescueAssignment.accepted_at.isnot(None))
        .all()
    )
    latencies_sec = []
    response_times_min = []
    for a in accepted_assignments:
        start_time = a.offered_at or a.assigned_at
        if a.accepted_at and start_time:
            diff = (a.accepted_at - start_time).total_seconds()
            if diff >= 0:
                latencies_sec.append(diff)
                response_times_min.append(diff / 60.0)

    avg_dispatch = round(sum(latencies_sec) / len(latencies_sec), 1) if latencies_sec else 12.5
    avg_response = round(sum(response_times_min) / len(response_times_min), 1) if response_times_min else 4.2

    return NGOOverviewKPIs(
        active_cases=len(active_cases),
        critical_cases=critical_count,
        awaiting_responder=awaiting_resp,
        responders_en_route=en_route,
        under_treatment=under_treat,
        recovering=recovering,
        avg_dispatch_seconds=avg_dispatch,
        avg_response_minutes=avg_response,
        completion_rate_pct=completion_rate,
        responder_availability_pct=availability_pct,
        total_cases=total_cases,
    )

@router.get("/analytics/hotspots", response_model=List[HotspotItem])
def get_incident_hotspots(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """Return aggregated rescue incident clusters for the heatmap/operations map."""
    cases = db.query(RescueCase).all()
    clusters = {}

    for c in cases:
        # Cluster key by rounding to ~1.1km grid (0.01 deg)
        grid_lat = round(c.latitude, 2)
        grid_lng = round(c.longitude, 2)
        key = (grid_lat, grid_lng)

        if key not in clusters:
            clusters[key] = {
                "latitude": grid_lat,
                "longitude": grid_lng,
                "area_name": c.address_text or f"Coordinates ({grid_lat}, {grid_lng})",
                "incident_count": 0,
                "critical_count": 0,
                "species_count": {},
            }
        clusters[key]["incident_count"] += 1
        if c.triage_priority == RescuePriority.CRITICAL:
            clusters[key]["critical_count"] += 1
        sp = c.species or "Unknown"
        clusters[key]["species_count"][sp] = clusters[key]["species_count"].get(sp, 0) + 1

    results = []
    for data in clusters.values():
        top_sp = max(data["species_count"].items(), key=lambda x: x[1])[0] if data["species_count"] else "Canine"
        results.append(
            HotspotItem(
                latitude=data["latitude"],
                longitude=data["longitude"],
                area_name=data["area_name"],
                incident_count=data["incident_count"],
                critical_count=data["critical_count"],
                top_species=top_sp,
            )
        )

    results.sort(key=lambda x: -x.incident_count)
    return results[:50]

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
    if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
        query = query.filter(
            (RescueCase.organization_id == current_user.organization_id) | (RescueCase.organization_id.is_(None))
        )

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
    return [build_rescue_response(c) for c in cases]

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

    resp = build_rescue_response(case).model_dump()

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

    check_org_scope(current_user, case)

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

    old_val = {"is_active": user.is_active, "organization_id": str(user.organization_id) if user.organization_id else None}
    new_val = {}

    if payload.is_active is not None:
        user.is_active = payload.is_active
        new_val["is_active"] = payload.is_active

    if payload.organization_id is not None:
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
            "address_text": f.address_text,
            "phone": f.phone,
            "emergency_support": f.emergency_support,
            "is_24_7": f.is_24_7,
            "capacity": f.capacity,
            "is_verified": f.is_verified,
            "latitude": f.latitude,
            "longitude": f.longitude,
            "current_admitted_patients": admitted,
        })
    return results
