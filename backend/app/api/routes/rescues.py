from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.user import User
from app.models.rescue_case import RescueCase
from app.models.rescue_status_history import RescueStatusHistory
from app.models.rescue_assignment import RescueAssignment
from app.schemas.rescue import (
    RescueCreate,
    RescueResponse,
    RescueStatusUpdate,
    RescueTimelineResponse,
    AnimalImageResponse,
    AssignedResponderResponse,
)
from app.api.dependencies import get_current_active_user
from app.services.rescue_service import RescueService
from app.services.dispatch_service import DispatchService
from app.core.permissions import RoleChecker
from app.core.constants import UserRole, RescueStatus, AssignmentStatus
from app.core.exceptions import NotFoundException, ConflictException, ForbiddenException

router = APIRouter()

def build_rescue_response(case: RescueCase, distance_km: Optional[float] = None) -> RescueResponse:
    # Build assigned responder info if assigned
    assigned_responder = None
    active_assignment = next(
        (a for a in case.assignments if a.assignment_status == AssignmentStatus.ACCEPTED),
        None
    )
    if active_assignment and active_assignment.rescuer:
        assigned_responder = AssignedResponderResponse(
            id=active_assignment.rescuer.id,
            full_name=active_assignment.rescuer.full_name,
            assignment_status=active_assignment.assignment_status.value,
            accepted_at=active_assignment.accepted_at
        )

    images = [
        AnimalImageResponse(
            id=img.id,
            image_url=img.image_url,
            image_type=img.image_type,
            created_at=img.created_at
        )
        for img in case.images
    ]

    return RescueResponse(
        id=case.id,
        case_number=case.case_number,
        animal_id=case.animal_id,
        reporter_id=case.reporter_id,
        species=case.species,
        description=case.description,
        latitude=case.latitude,
        longitude=case.longitude,
        address_text=case.address_text,
        triage_score=case.triage_score,
        triage_priority=case.triage_priority,
        triage_reason=case.triage_reason,
        status=case.status,
        veterinary_facility_id=case.veterinary_facility_id,
        created_at=case.created_at,
        updated_at=case.updated_at,
        closed_at=case.closed_at,
        distance_km=distance_km,
        dispatch_radius_km=case.dispatch_radius_km,
        dispatch_attempt=case.dispatch_attempt,
        images=images,
        assigned_responder=assigned_responder
    )

def verify_case_access(case: RescueCase, user: User) -> None:
    """Enforce strict access rules for cases."""
    if user.role in [UserRole.SUPER_ADMIN, UserRole.NGO_ADMIN, UserRole.MUNICIPAL_ADMIN]:
        return
    if user.role == UserRole.CITIZEN:
        if case.reporter_id != user.id:
            raise ForbiddenException("Citizens can only access their own reported rescue cases.")
        return
    if user.role == UserRole.RESCUER:
        # Rescuers can view cases that are open or assigned to them
        is_assigned = any(
            a.rescuer_id == user.id for a in case.assignments
        )
        is_open = case.status in [
            RescueStatus.REPORTED,
            RescueStatus.TRIAGED,
            RescueStatus.SEARCHING_RESPONDER,
            RescueStatus.RESPONDER_ASSIGNED,
            RescueStatus.RESPONDER_EN_ROUTE,
            RescueStatus.ANIMAL_LOCATED,
            RescueStatus.RESCUED,
            RescueStatus.TRANSPORTING
        ]
        if not is_assigned and not is_open:
            raise ForbiddenException("Rescuers cannot view unrelated private cases.")
        return
    if user.role == UserRole.VETERINARIAN:
        # Veterinarians can view cases that are at a veterinary facility or under treatment
        if case.status not in [
            RescueStatus.AT_VETERINARY_FACILITY,
            RescueStatus.UNDER_TREATMENT,
            RescueStatus.RECOVERING,
            RescueStatus.READY_FOR_RELEASE,
            RescueStatus.READY_FOR_ADOPTION,
            RescueStatus.CLOSED
        ]:
            raise ForbiddenException("Veterinarians can only view cases referred to veterinary care.")

        # Requirement 43: Enforce authorized veterinary facility scoping
        if user.veterinary_facility_id and case.veterinary_facility_id:
            if case.veterinary_facility_id != user.veterinary_facility_id:
                raise ForbiddenException("Veterinarians can only view cases assigned to their authorized facility.")
        return
    raise ForbiddenException("Access denied.")

@router.post("", response_model=RescueResponse)
def create_rescue(
    case_in: RescueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = RescueService.create_case(db, current_user.id, case_in)
    return build_rescue_response(case)

@router.get("/my", response_model=List[RescueResponse])
def get_my_rescues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    cases = db.query(RescueCase).filter(RescueCase.reporter_id == current_user.id).order_by(RescueCase.created_at.desc()).all()
    return [build_rescue_response(c) for c in cases]

@router.get("/nearby", response_model=List[RescueResponse])
def get_nearby_rescues(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lng: float = Query(..., ge=-180.0, le=180.0),
    radius_km: float = Query(10.0, gt=0, le=100.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER, UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    results = DispatchService.find_nearby_rescues(db, lat, lng, radius_km)
    return [build_rescue_response(case, dist) for case, dist in results]

@router.get("/{case_id}", response_model=RescueResponse)
def get_rescue(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise NotFoundException("Rescue case not found")
    verify_case_access(case, current_user)
    return build_rescue_response(case)

@router.get("/{case_id}/timeline", response_model=List[RescueTimelineResponse])
def get_rescue_timeline(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise NotFoundException("Rescue case not found")
    verify_case_access(case, current_user)
    history = (
        db.query(RescueStatusHistory)
        .filter(RescueStatusHistory.rescue_case_id == case_id)
        .order_by(RescueStatusHistory.created_at.asc())
        .all()
    )
    return history

@router.post("/{case_id}/accept", response_model=dict)
def accept_rescue(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER]))
):
    # Concurrency row-locking
    case = db.query(RescueCase).filter(RescueCase.id == case_id).with_for_update().first()
    if not case:
        raise NotFoundException("Rescue case not found")
    
    if case.status not in [RescueStatus.TRIAGED, RescueStatus.SEARCHING_RESPONDER]:
        raise ConflictException("This rescue has already been assigned to another responder or is closed.")
    
    # Check existing active assignment
    existing_assignment = (
        db.query(RescueAssignment)
        .filter(
            RescueAssignment.rescue_case_id == case.id,
            RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED
        )
        .first()
    )
    if existing_assignment:
        raise ConflictException("This rescue has already been assigned to another responder.")
    
    # Create assignment record
    assignment = RescueAssignment(
        rescue_case_id=case.id,
        rescuer_id=current_user.id,
        accepted_at=datetime.utcnow(),
        assignment_status=AssignmentStatus.ACCEPTED
    )
    db.add(assignment)
    
    # Update case status
    RescueService.update_status(
        db,
        case,
        RescueStatus.RESPONDER_ASSIGNED,
        current_user.id,
        notes=f"Accepted by responder {current_user.full_name}"
    )
    
    return {"success": True, "message": "Rescue accepted successfully"}

@router.patch("/{case_id}/status", response_model=RescueResponse)
def update_status(
    case_id: UUID,
    status_update: RescueStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([
        UserRole.RESCUER,
        UserRole.VETERINARIAN,
        UserRole.NGO_ADMIN,
        UserRole.SUPER_ADMIN,
        UserRole.CITIZEN
    ]))
):
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise NotFoundException("Rescue case not found")
        
    updated_case = RescueService.update_status(
        db,
        case,
        status_update.status,
        current_user.id,
        notes=status_update.notes,
        veterinary_facility_id=status_update.veterinary_facility_id
    )
    return build_rescue_response(updated_case)
