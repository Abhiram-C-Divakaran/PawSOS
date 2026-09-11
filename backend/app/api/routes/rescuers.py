from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models.user import User
from app.models.rescuer_profile import RescuerProfile
from app.schemas.rescuer import RescuerLocationUpdate, RescuerAvailabilityUpdate, RescuerProfileResponse
from app.core.permissions import RoleChecker
from app.core.constants import UserRole, RescuerAvailability

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
