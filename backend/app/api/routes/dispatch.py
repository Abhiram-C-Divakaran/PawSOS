import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.core.permissions import RoleChecker
from app.core.constants import UserRole
from app.schemas.dispatch import DispatchOfferResponse, DispatchRejectRequest
from app.services.dispatch_service import DispatchService

router = APIRouter()

@router.post("/{offer_id}/accept", response_model=DispatchOfferResponse)
def accept_offer(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER]))
):
    """Accept a pending dispatch offer."""
    return DispatchService.accept_offer(db, offer_id, current_user.id)

@router.post("/{offer_id}/reject", response_model=DispatchOfferResponse)
def reject_offer(
    offer_id: uuid.UUID,
    payload: DispatchRejectRequest = DispatchRejectRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER]))
):
    """Decline a dispatch offer with optional reason."""
    return DispatchService.reject_offer(db, offer_id, current_user.id, reason=payload.reason)
