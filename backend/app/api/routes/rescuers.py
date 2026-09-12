import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.rescuer_profile import RescuerProfile
from app.models.rescue_assignment import RescueAssignment
from app.schemas.rescuer import RescuerLocationUpdate, RescuerAvailabilityUpdate, RescuerProfileResponse
from app.schemas.dispatch import DispatchOfferResponse, DispatchRejectRequest
from app.services.dispatch_service import DispatchService
from app.core.permissions import RoleChecker
from app.core.constants import UserRole, RescuerAvailability, AssignmentStatus

router = APIRouter()

def get_or_create_rescuer_profile(db: Session, user: User) -> RescuerProfile:
    profile = db.query(RescuerProfile).filter(RescuerProfile.user_id == user.id).first()
    if not profile:
        profile = RescuerProfile(
            user_id=user.id,
            availability_status=RescuerAvailability.AVAILABLE,
            organization_id=user.organization_id,
            last_location_update=datetime.utcnow()
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile

@router.get("/me/profile", response_model=RescuerProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER]))
):
    profile = get_or_create_rescuer_profile(db, current_user)
    return profile

@router.patch("/me/location", response_model=RescuerProfileResponse)
def update_my_location(
    loc_in: RescuerLocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER]))
):
    profile = get_or_create_rescuer_profile(db, current_user)
    profile.latitude = loc_in.latitude
    profile.longitude = loc_in.longitude
    profile.current_location = f"POINT({loc_in.longitude} {loc_in.latitude})"
    profile.last_location_update = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return profile

@router.patch("/me/availability", response_model=RescuerProfileResponse)
def update_my_availability(
    avail_in: RescuerAvailabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER]))
):
    profile = get_or_create_rescuer_profile(db, current_user)
    profile.availability_status = avail_in.availability_status
    db.commit()
    db.refresh(profile)
    return profile

@router.get("/me/offers", response_model=List[DispatchOfferResponse])
def get_my_dispatch_offers(
    status: str = "PENDING",
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER]))
):
    """Retrieve dispatch offers sent to the authenticated responder."""
    # First check & expire any stale offers in background
    DispatchService.expire_stale_offers(db)

    query = (
        db.query(RescueAssignment)
        .filter(RescueAssignment.rescuer_id == current_user.id)
    )
    if status.upper() == "PENDING":
        query = query.filter(
            RescueAssignment.assignment_status == AssignmentStatus.PENDING,
            (RescueAssignment.expires_at.is_(None)) | (RescueAssignment.expires_at > datetime.utcnow())
        )
    elif status.upper() != "ALL":
        query = query.filter(RescueAssignment.assignment_status == status)

    offers = query.order_by(RescueAssignment.offered_at.desc()).all()
    return offers

@router.post("/offers/{offer_id}/accept", response_model=DispatchOfferResponse)
def accept_dispatch_offer(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER]))
):
    """Accept a pending dispatch offer with concurrency protection."""
    return DispatchService.accept_offer(db, offer_id, current_user.id)

@router.post("/offers/{offer_id}/reject", response_model=DispatchOfferResponse)
def reject_dispatch_offer(
    offer_id: uuid.UUID,
    payload: DispatchRejectRequest = DispatchRejectRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER]))
):
    """Decline a dispatch offer with optional reason."""
    return DispatchService.reject_offer(db, offer_id, current_user.id, reason=payload.reason)

