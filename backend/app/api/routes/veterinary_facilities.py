from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.user import User
from app.models.veterinary_facility import VeterinaryFacility
from app.models.rescue_case import RescueCase
from app.schemas.veterinary import VeterinaryFacilityResponse
from app.schemas.rescue import RescueResponse
from app.api.routes.rescues import build_rescue_response
from app.core.permissions import RoleChecker
from app.core.constants import UserRole, RescueStatus
from app.core.exceptions import NotFoundException, BadRequestException, ForbiddenException
from app.services.rescue_service import RescueService

router = APIRouter()

@router.get("/facilities", response_model=List[VeterinaryFacilityResponse])
def get_veterinary_facilities(
    db: Session = Depends(get_db)
):
    """List verified veterinary facilities for responders to select transport destination."""
    facilities = db.query(VeterinaryFacility).filter(VeterinaryFacility.is_verified == True).all()
    # Fallback to all facilities if none explicitly verified in dev
    if not facilities:
        facilities = db.query(VeterinaryFacility).all()
    return facilities

@router.get("/cases", response_model=List[RescueResponse])
def get_veterinary_cases(
    facility_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.VETERINARIAN, UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    """
    Veterinary inbox: returns cases that have arrived at a facility,
    are currently under medical treatment, or recovering.
    """
    vet_statuses = [
        RescueStatus.AT_VETERINARY_FACILITY,
        RescueStatus.UNDER_TREATMENT,
        RescueStatus.RECOVERING
    ]
    query = db.query(RescueCase).filter(RescueCase.status.in_(vet_statuses))

    # Facility scoping: Veterinarians can only access cases assigned to their authorized facility
    if current_user.role == UserRole.VETERINARIAN:
        if not current_user.veterinary_facility_id:
            raise ForbiddenException("Access denied: Veterinarian is not associated with an authorized facility.")
        query = query.filter(RescueCase.veterinary_facility_id == current_user.veterinary_facility_id)
    elif current_user.role == UserRole.NGO_ADMIN:
        if not current_user.organization_id:
            raise ForbiddenException("Access denied: NGO Admin is not associated with an organization.")
        query = query.filter(RescueCase.organization_id == current_user.organization_id)
        if facility_id:
            query = query.filter(RescueCase.veterinary_facility_id == facility_id)
    elif facility_id:
        query = query.filter(RescueCase.veterinary_facility_id == facility_id)

    cases = query.order_by(RescueCase.updated_at.desc()).all()
    return [build_rescue_response(c, include_evidence=True, presign_images=False) for c in cases]
