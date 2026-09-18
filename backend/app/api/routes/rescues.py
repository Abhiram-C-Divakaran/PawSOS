from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.user import User
from app.models.rescue_case import RescueCase
from app.models.rescue_status_history import RescueStatusHistory
from app.models.rescue_assignment import RescueAssignment
import json
import logging
from app.schemas.rescue import (
    RescueCreate,
    RescueResponse,
    RescueDiscoverySummary,
    RescueStatusUpdate,
    RescueTimelineResponse,
    AnimalImageResponse,
    AssignedResponderResponse,
    TriageDetailResponse,
    RuleAssessmentDetail,
    AIAssessmentDetail,
)
from app.api.dependencies import get_current_active_user
from app.services.rescue_service import RescueService
from app.services.dispatch_service import DispatchService
from app.services.triage_service import TriageService
from app.models.triage_assessment import TriageAssessment
from app.core.permissions import RoleChecker
from app.core.constants import UserRole, RescueStatus, AssignmentStatus
from app.core.exceptions import NotFoundException, ConflictException, ForbiddenException, ServiceUnavailableException
from app.core.rate_limiter import limiter
from app.config import settings

from app.services.storage_service import storage_service
from app.core.case_access import (
    verify_case_access,
    can_view_case_private_details,
    can_access_case_evidence,
)

logger = logging.getLogger(__name__)

router = APIRouter()

def build_rescue_response(
    case: RescueCase,
    distance_km: Optional[float] = None,
    include_evidence: bool = True,
    presign_images: bool = False,
) -> RescueResponse:
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

    if not include_evidence:
        images = []
    else:
        images = []
        for img in case.images:
            if presign_images:
                img_url = storage_service.get_presigned_url(
                    img.image_url,
                    expires_in=settings.S3_PRESIGNED_URL_EXPIRE_SECONDS
                )
            else:
                # If local file, provide the relative /uploads/ path
                if img.image_url.startswith("/uploads/") or img.image_url.startswith("http://") or img.image_url.startswith("https://"):
                    img_url = img.image_url
                elif settings.STORAGE_PROVIDER == "local":
                    img_url = storage_service.get_presigned_url(img.image_url)
                else:
                    # In S3 storage provider without explicit presigning, keep canonical key
                    img_url = img.image_url

            images.append(
                AnimalImageResponse(
                    id=img.id,
                    image_url=img_url,
                    image_type=img.image_type,
                    created_at=img.created_at
                )
            )

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

@router.get("/{case_id}/images/{image_id}/access", response_model=dict)
def get_rescue_image_access(
    case_id: UUID,
    image_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Authorized evidence-image access endpoint.
    Validates tenant and user authorization before returning a short-lived presigned GET URL.
    """
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise NotFoundException("Rescue case not found")

    verify_case_access(case, current_user, db)

    target_image = next((img for img in case.images if img.id == image_id), None)
    if not target_image:
        raise NotFoundException("Animal image not found for this case")

    signed_url = storage_service.get_presigned_url(
        target_image.image_url,
        expires_in=settings.S3_PRESIGNED_URL_EXPIRE_SECONDS
    )
    return {
        "url": signed_url,
        "expires_in": settings.S3_PRESIGNED_URL_EXPIRE_SECONDS
    }

@router.post("", response_model=RescueResponse)
def create_rescue(
    case_in: RescueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = RescueService.create_case(db, current_user.id, case_in)
    return build_rescue_response(case, include_evidence=True, presign_images=False)

@router.get("/my", response_model=List[RescueResponse])
def get_my_rescues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    cases = db.query(RescueCase).filter(RescueCase.reporter_id == current_user.id).order_by(RescueCase.created_at.desc()).all()
    return [build_rescue_response(c, include_evidence=True, presign_images=False) for c in cases]

@router.get("/nearby", response_model=List[RescueDiscoverySummary])
def get_nearby_rescues(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lng: float = Query(..., ge=-180.0, le=180.0),
    radius_km: float = Query(10.0, gt=0, le=100.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.RESCUER, UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    results = DispatchService.find_nearby_rescues(db, lat, lng, radius_km)
    return [
        RescueDiscoverySummary(
            id=case.id,
            case_number=case.case_number,
            species=case.species,
            triage_priority=case.triage_priority,
            status=case.status,
            distance_km=dist,
            created_at=case.created_at,
            coarse_location=None,
        )
        for case, dist in results
    ]

@router.get("/{case_id}", response_model=RescueResponse)
def get_rescue(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise NotFoundException("Rescue case not found")
    verify_case_access(case, current_user, db)
    return build_rescue_response(case, include_evidence=True, presign_images=False)

@router.get("/{case_id}/timeline", response_model=List[RescueTimelineResponse])
def get_rescue_timeline(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise NotFoundException("Rescue case not found")
    verify_case_access(case, current_user, db)
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
    """
    Backwards-compatible secure shim for rescue case acceptance.
    Strictly requires an active, unexpired PENDING dispatch offer issued to the authenticated responder.
    Delegates to canonical DispatchService.accept_offer for single-winner row locking and offer resolution.
    """
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise NotFoundException("Rescue case not found")

    # If the case is already assigned to another responder or closed, fail with Conflict
    if case.status not in [RescueStatus.TRIAGED, RescueStatus.SEARCHING_RESPONDER]:
        raise ConflictException("This rescue has already been assigned to another responder or is closed.")

    now = datetime.utcnow()
    # Locate any offer for this rescuer on this case
    any_offer = (
        db.query(RescueAssignment)
        .filter(
            RescueAssignment.rescue_case_id == case.id,
            RescueAssignment.rescuer_id == current_user.id,
        )
        .first()
    )

    if not any_offer:
        # Caller has no offer at all for this case -> fail-closed
        raise ForbiddenException("No active dispatch offer found for this rescuer on this case")

    if any_offer.assignment_status != AssignmentStatus.PENDING:
        raise ConflictException(f"Offer is no longer pending (current status: {any_offer.assignment_status.value})")

    if any_offer.expires_at and any_offer.expires_at <= now:
        raise ConflictException("Dispatch offer has expired")

    # Delegate to canonical transactional acceptance logic
    accepted_offer = DispatchService.accept_offer(db, any_offer.id, current_user.id)

    return {
        "success": True,
        "message": "Rescue accepted successfully",
        "assignment_id": str(accepted_offer.id),
        "rescue_case_id": str(case.id),
    }

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
    return build_rescue_response(updated_case, include_evidence=True, presign_images=False)


@router.get("/{case_id}/triage", response_model=TriageDetailResponse)
def get_rescue_triage(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise NotFoundException("Rescue case not found")

    verify_case_access(case, current_user, db)

    # Compute deterministic rule assessment
    rule_calc = TriageService.calculate_triage({
        "bleeding": case.bleeding,
        "can_walk": case.can_walk,
        "conscious": case.conscious,
        "vehicle_accident": case.vehicle_accident,
        "breathing_difficulty": case.breathing_difficulty,
    })
    rule_detail = RuleAssessmentDetail(
        priority=rule_calc["priority"],
        score=rule_calc["score"],
        reasons=rule_calc["reasons"],
    )

    # Fetch latest triage assessment if present
    latest_assessment = (
        db.query(TriageAssessment)
        .filter(TriageAssessment.rescue_case_id == case.id)
        .order_by(TriageAssessment.created_at.desc())
        .first()
    )

    if not latest_assessment:
        if not settings.AI_TRIAGE_ENABLED or settings.AI_TRIAGE_PROVIDER == "disabled":
            ai_detail = AIAssessmentDetail(
                status="NOT_REQUESTED",
                source="IMAGE_AI",
                provider="disabled",
                explanation="Visual AI triage is disabled in system configuration.",
            )
        elif not case.images:
            ai_detail = AIAssessmentDetail(
                status="NOT_REQUESTED",
                source="IMAGE_AI",
                provider=settings.AI_TRIAGE_PROVIDER,
                explanation="No evidence image attached to rescue report.",
            )
        else:
            ai_detail = AIAssessmentDetail(
                status="NOT_REQUESTED",
                source="IMAGE_AI",
                provider=settings.AI_TRIAGE_PROVIDER,
                explanation="Visual AI triage was not requested for this case.",
            )
    else:
        signs = []
        if latest_assessment.visible_signs:
            try:
                parsed = json.loads(latest_assessment.visible_signs)
                if isinstance(parsed, list):
                    signs = parsed
                else:
                    signs = [str(parsed)]
            except Exception:
                signs = [latest_assessment.visible_signs]

        ai_detail = AIAssessmentDetail(
            status=latest_assessment.status,
            source=latest_assessment.source,
            suggested_priority=latest_assessment.suggested_priority,
            score=latest_assessment.score,
            confidence=latest_assessment.confidence,
            visible_signs=signs,
            explanation=latest_assessment.explanation,
            provider=latest_assessment.provider,
            model_name=latest_assessment.model_name,
            model_version=latest_assessment.model_version,
            created_at=latest_assessment.created_at,
            completed_at=latest_assessment.completed_at,
        )

    return TriageDetailResponse(
        case_id=case.id,
        case_number=case.case_number,
        final_priority=case.triage_priority or rule_detail.priority,
        final_score=case.triage_score if case.triage_score is not None else rule_detail.score,
        final_reason=case.triage_reason or ", ".join(rule_detail.reasons),
        rule_assessment=rule_detail,
        ai_assessment=ai_detail,
    )


@router.post("/{case_id}/triage/retry", response_model=dict)
@limiter.limit("5/minute")
def retry_rescue_triage(
    request: Request,
    case_id: UUID,
    force: bool = Query(False, description="Force retry even if previously completed"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise NotFoundException("Rescue case not found")

    verify_case_access(case, current_user, db)

    if not settings.AI_TRIAGE_ENABLED or settings.AI_TRIAGE_PROVIDER == "disabled":
        raise ConflictException("Visual triage is not enabled for this environment.")

    if not case.images:
        raise ConflictException("No evidence image attached to rescue case to assess.")

    image = case.images[0]

    model_name = settings.AI_TRIAGE_MODEL_NAME
    model_version = settings.AI_TRIAGE_MODEL_VERSION

    existing = (
        db.query(TriageAssessment)
        .filter(
            TriageAssessment.rescue_case_id == case.id,
            TriageAssessment.model_name == model_name,
            TriageAssessment.model_version == model_version,
        )
        .first()
    )

    if existing and existing.status == "COMPLETED" and not force:
        return {
            "success": True,
            "message": "Visual assessment is already completed. Use force=true to re-run.",
            "status": "COMPLETED",
        }

    if not existing:
        existing = TriageAssessment(
            rescue_case_id=case.id,
            animal_image_id=image.id,
            source="IMAGE_AI",
            status="PENDING",
            provider=settings.AI_TRIAGE_PROVIDER,
            model_name=model_name,
            model_version=model_version,
            explanation="Visual assessment queued for execution.",
        )
        db.add(existing)
    else:
        existing.status = "PENDING"
        existing.sanitized_error_code = None
        existing.explanation = "Visual assessment queued for execution."
        existing.completed_at = None

    db.commit()
    db.refresh(existing)

    try:
        from app.tasks.ai_triage_tasks import perform_ai_triage_task
        perform_ai_triage_task.delay(str(case.id), str(image.id))
    except Exception:
        logger.error(
            "[AI_TRIAGE_RETRY] Failed to enqueue visual triage task for case_id=%s, case_number=%s",
            str(case.id),
            case.case_number,
            exc_info=True,
        )
        existing.status = "FAILED"
        existing.sanitized_error_code = "QUEUE_ERROR"
        existing.explanation = "Visual triage service is temporarily unavailable."
        existing.completed_at = datetime.utcnow()
        db.commit()
        raise ServiceUnavailableException("Visual triage service is temporarily unavailable.")

    return {
        "success": True,
        "message": "Visual triage assessment queued for execution.",
        "status": "PENDING",
    }


