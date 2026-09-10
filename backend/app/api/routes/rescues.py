from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from app.database import get_db
from app.models.user import User
from app.models.rescue_case import RescueCase
from app.models.rescue_status_history import RescueStatusHistory
from app.models.rescue_assignment import RescueAssignment
from app.schemas.rescue import RescueCreate, RescueResponse, RescueStatusUpdate, RescueTimelineResponse
from app.api.dependencies import get_current_active_user
from app.services.rescue_service import RescueService
from app.services.dispatch_service import DispatchService
from app.core.permissions import RoleChecker
from app.core.constants import UserRole, RescueStatus, AssignmentStatus
from app.core.exceptions import NotFoundException, ConflictException, ForbiddenException
from datetime import datetime

router = APIRouter()

@router.post("", response_model=RescueResponse)
def create_rescue(
    case_in: RescueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = RescueService.create_case(db, current_user.id, case_in)
    return case

@router.get("/my", response_model=List[RescueResponse])
def get_my_rescues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    return db.query(RescueCase).filter(RescueCase.reporter_id == current_user.id).all()

@router.get("/nearby", response_model=List[RescueResponse])
def get_nearby_rescues(
    lat: float,
    lng: float,
    radius_km: float = 5.0,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER, UserRole.NGO_ADMIN]))
):
    # Mocking geospatial for MVP: return open cases
    cases = db.query(RescueCase).filter(
        RescueCase.status.in_([RescueStatus.TRIAGED, RescueStatus.SEARCHING_RESPONDER])
    ).all()
    return cases

@router.get("/{case_id}", response_model=RescueResponse)
def get_rescue(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise NotFoundException("Rescue case not found")
    return case

@router.get("/{case_id}/timeline", response_model=List[RescueTimelineResponse])
def get_rescue_timeline(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    history = db.query(RescueStatusHistory).filter(RescueStatusHistory.rescue_case_id == case_id).order_by(RescueStatusHistory.created_at.asc()).all()
    return history

@router.post("/{case_id}/accept", response_model=dict)
def accept_rescue(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER]))
):
    case = db.query(RescueCase).filter(RescueCase.id == case_id).with_for_update().first()
    if not case:
        raise NotFoundException("Rescue case not found")
    
    if case.status not in [RescueStatus.TRIAGED, RescueStatus.SEARCHING_RESPONDER]:
        raise ConflictException("Rescue case is already assigned or closed")
    
    # Create assignment
    assignment = RescueAssignment(
        rescue_case_id=case.id,
        rescuer_id=current_user.id,
        accepted_at=datetime.utcnow(),
        assignment_status=AssignmentStatus.ACCEPTED
    )
    db.add(assignment)
    
    # Update case status
    RescueService.update_status(db, case, RescueStatus.RESPONDER_ASSIGNED, current_user.id, notes="Rescuer accepted")
    
    return {"success": True, "message": "Rescue accepted successfully"}

@router.patch("/{case_id}/status", response_model=RescueResponse)
def update_status(
    case_id: UUID,
    status_update: RescueStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER, UserRole.VETERINARIAN, UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise NotFoundException("Rescue case not found")
        
    updated_case = RescueService.update_status(db, case, status_update.status, current_user.id, notes=status_update.notes)
    return updated_case
