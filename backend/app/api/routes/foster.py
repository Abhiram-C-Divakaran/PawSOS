import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.foster_home import FosterHome
from app.models.foster_assignment import FosterAssignment
from app.models.foster_care_update import FosterCareUpdate
from app.models.rescue_case import RescueCase
from app.models.audit_log import AuditLog
from app.core.constants import UserRole, FosterAssignmentStatus
from app.api.dependencies import get_current_active_user as get_current_user
from app.services.foster_service import FosterService
from app.schemas.foster import (
    FosterHomeCreate,
    FosterHomeUpdate,
    FosterHomePrivateResponse,
    FosterHomeSafeResponse,
    FosterAssignmentCreate,
    FosterAssignmentResponse,
    FosterCareUpdateCreate,
    FosterCareUpdateResponse,
    FosterMatchRequest,
    FosterMatchCandidate,
)

router = APIRouter()

# ============================================================================
# FOSTER CAREGIVER PROFILE & ASSIGNMENT ENDPOINTS
# ============================================================================

@router.get("/profile", response_model=FosterHomePrivateResponse)
def get_foster_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    home = db.query(FosterHome).filter(FosterHome.caregiver_id == current_user.id).first()
    if not home:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster profile not found")
    
    return FosterHomePrivateResponse(
        id=home.id,
        caregiver_id=home.caregiver_id,
        organization_id=home.organization_id,
        locality=home.locality,
        latitude=home.latitude,
        longitude=home.longitude,
        capacity=home.capacity,
        current_occupancy=home.current_occupancy,
        accepted_species=home.accepted_species,
        maximum_animal_size=home.maximum_animal_size,
        medical_care_supported=home.medical_care_supported,
        availability_status=home.availability_status,
        verified=home.verified,
        verified_at=home.verified_at,
        verified_by_user_id=home.verified_by_user_id,
        caregiver_name=current_user.full_name,
        caregiver_phone=current_user.phone,
        caregiver_email=current_user.email,
        created_at=home.created_at,
    )


@router.post("/profile", response_model=FosterHomePrivateResponse)
def create_foster_profile(
    payload: FosterHomeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(FosterHome).filter(FosterHome.caregiver_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Foster profile already exists")

    home = FosterHome(
        caregiver_id=current_user.id,
        organization_id=current_user.organization_id,
        locality=payload.locality,
        latitude=payload.latitude,
        longitude=payload.longitude,
        capacity=payload.capacity,
        current_occupancy=0,
        accepted_species=payload.accepted_species,
        maximum_animal_size=payload.maximum_animal_size,
        medical_care_supported=payload.medical_care_supported,
        availability_status=payload.availability_status or "AVAILABLE",
        verified=False,  # Self-verification strictly prohibited
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(home)
    db.commit()
    db.refresh(home)

    return FosterHomePrivateResponse(
        id=home.id,
        caregiver_id=home.caregiver_id,
        organization_id=home.organization_id,
        locality=home.locality,
        latitude=home.latitude,
        longitude=home.longitude,
        capacity=home.capacity,
        current_occupancy=home.current_occupancy,
        accepted_species=home.accepted_species,
        maximum_animal_size=home.maximum_animal_size,
        medical_care_supported=home.medical_care_supported,
        availability_status=home.availability_status,
        verified=home.verified,
        verified_at=home.verified_at,
        verified_by_user_id=home.verified_by_user_id,
        caregiver_name=current_user.full_name,
        caregiver_phone=current_user.phone,
        caregiver_email=current_user.email,
        created_at=home.created_at,
    )


@router.patch("/profile", response_model=FosterHomePrivateResponse)
def update_foster_profile(
    payload: FosterHomeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    home = db.query(FosterHome).filter(FosterHome.caregiver_id == current_user.id).first()
    if not home:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster profile not found")

    if payload.locality is not None:
        home.locality = payload.locality
    if payload.latitude is not None:
        home.latitude = payload.latitude
    if payload.longitude is not None:
        home.longitude = payload.longitude
    if payload.capacity is not None:
        if payload.capacity < home.current_occupancy:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Capacity cannot be less than current occupancy")
        home.capacity = payload.capacity
    if payload.accepted_species is not None:
        home.accepted_species = payload.accepted_species
    if payload.maximum_animal_size is not None:
        home.maximum_animal_size = payload.maximum_animal_size
    if payload.medical_care_supported is not None:
        home.medical_care_supported = payload.medical_care_supported
    if payload.availability_status is not None:
        home.availability_status = payload.availability_status

    home.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(home)

    return FosterHomePrivateResponse(
        id=home.id,
        caregiver_id=home.caregiver_id,
        organization_id=home.organization_id,
        locality=home.locality,
        latitude=home.latitude,
        longitude=home.longitude,
        capacity=home.capacity,
        current_occupancy=home.current_occupancy,
        accepted_species=home.accepted_species,
        maximum_animal_size=home.maximum_animal_size,
        medical_care_supported=home.medical_care_supported,
        availability_status=home.availability_status,
        verified=home.verified,
        verified_at=home.verified_at,
        verified_by_user_id=home.verified_by_user_id,
        caregiver_name=current_user.full_name,
        caregiver_phone=current_user.phone,
        caregiver_email=current_user.email,
        created_at=home.created_at,
    )


@router.get("/assignments", response_model=List[FosterAssignmentResponse])
def list_foster_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    home = db.query(FosterHome).filter(FosterHome.caregiver_id == current_user.id).first()
    if not home:
        return []

    assignments = (
        db.query(FosterAssignment)
        .filter(FosterAssignment.foster_home_id == home.id)
        .order_by(FosterAssignment.start_date.desc())
        .all()
    )

    results = []
    for a in assignments:
        case = a.rescue_case
        animal = a.animal
        results.append(
            FosterAssignmentResponse(
                id=a.id,
                animal_id=a.animal_id,
                rescue_case_id=a.rescue_case_id,
                foster_home_id=a.foster_home_id,
                start_date=a.start_date,
                expected_end_date=a.expected_end_date,
                actual_end_date=a.actual_end_date,
                status=a.status,
                notes=a.notes,
                created_at=getattr(a, "created_at", None),
                animal_species=animal.species if animal else (case.species if case else None),
                animal_description=animal.description if animal else (case.description if case else None),
                case_number=case.case_number if case else None,
                foster_home_locality=home.locality,
                caregiver_name=current_user.full_name,
            )
        )
    return results


@router.post("/assignments/{assignment_id}/accept", response_model=FosterAssignmentResponse)
def accept_foster_assignment(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = FosterService.accept_offer(db=db, current_user=current_user, assignment_id=assignment_id)
    return FosterAssignmentResponse(
        id=assignment.id,
        animal_id=assignment.animal_id,
        rescue_case_id=assignment.rescue_case_id,
        foster_home_id=assignment.foster_home_id,
        start_date=assignment.start_date,
        expected_end_date=assignment.expected_end_date,
        actual_end_date=assignment.actual_end_date,
        status=assignment.status,
        notes=assignment.notes,
        created_at=getattr(assignment, "created_at", None),
    )


@router.post("/assignments/{assignment_id}/decline", response_model=FosterAssignmentResponse)
def decline_foster_assignment(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = FosterService.decline_offer(db=db, current_user=current_user, assignment_id=assignment_id)
    return FosterAssignmentResponse(
        id=assignment.id,
        animal_id=assignment.animal_id,
        rescue_case_id=assignment.rescue_case_id,
        foster_home_id=assignment.foster_home_id,
        start_date=assignment.start_date,
        expected_end_date=assignment.expected_end_date,
        actual_end_date=assignment.actual_end_date,
        status=assignment.status,
        notes=assignment.notes,
        created_at=getattr(assignment, "created_at", None),
    )


@router.post("/assignments/{assignment_id}/care-updates", response_model=FosterCareUpdateResponse)
def submit_care_update(
    assignment_id: uuid.UUID,
    payload: FosterCareUpdateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = db.query(FosterAssignment).filter(FosterAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster assignment not found")

    home = db.query(FosterHome).filter(FosterHome.id == assignment.foster_home_id).first()
    if not home:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster home not found")

    # Authorization: Caregiver, managing NGO, or Admin
    is_caregiver = home.caregiver_id == current_user.id
    is_ngo = (
        current_user.role == UserRole.NGO_ADMIN and
        current_user.organization_id is not None and
        home.organization_id == current_user.organization_id
    )
    is_admin = current_user.role in [UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]

    if not (is_caregiver or is_ngo or is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to submit care update")

    # Caregivers can record observations and recommendations, but NOT formal veterinary diagnosis
    update = FosterCareUpdate(
        assignment_id=assignment.id,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
        general_notes=payload.general_notes,
        appetite_status=payload.appetite_status,
        activity_status=payload.activity_status,
        weight_kg=payload.weight_kg,
        medication_administered=payload.medication_administered,
        concern_flag=payload.concern_flag,
        readiness_recommendation=payload.readiness_recommendation,
    )
    db.add(update)

    audit = AuditLog(
        actor_id=current_user.id,
        action="FOSTER_CARE_UPDATE_SUBMITTED",
        entity="foster_care_update",
        entity_id=update.id,
        new_value={"concern_flag": payload.concern_flag, "recommendation": payload.readiness_recommendation},
        timestamp=datetime.utcnow(),
    )
    db.add(audit)
    db.commit()
    db.refresh(update)

    return FosterCareUpdateResponse(
        id=update.id,
        assignment_id=update.assignment_id,
        created_by=update.created_by,
        created_at=update.created_at,
        general_notes=update.general_notes,
        appetite_status=update.appetite_status,
        activity_status=update.activity_status,
        weight_kg=update.weight_kg,
        medication_administered=update.medication_administered,
        concern_flag=update.concern_flag,
        readiness_recommendation=update.readiness_recommendation,
        author_name=current_user.full_name,
    )


@router.get("/assignments/{assignment_id}/care-updates", response_model=List[FosterCareUpdateResponse])
def get_care_updates(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = db.query(FosterAssignment).filter(FosterAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster assignment not found")

    home = db.query(FosterHome).filter(FosterHome.id == assignment.foster_home_id).first()
    if not home:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster home not found")

    is_caregiver = home.caregiver_id == current_user.id
    is_ngo = (
        current_user.role == UserRole.NGO_ADMIN and
        current_user.organization_id is not None and
        home.organization_id == current_user.organization_id
    )
    is_admin = current_user.role in [UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]

    if not (is_caregiver or is_ngo or is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    updates = (
        db.query(FosterCareUpdate)
        .filter(FosterCareUpdate.assignment_id == assignment.id)
        .order_by(FosterCareUpdate.created_at.desc())
        .all()
    )

    results = []
    for u in updates:
        results.append(
            FosterCareUpdateResponse(
                id=u.id,
                assignment_id=u.assignment_id,
                created_by=u.created_by,
                created_at=u.created_at,
                general_notes=u.general_notes,
                appetite_status=u.appetite_status,
                activity_status=u.activity_status,
                weight_kg=u.weight_kg,
                medication_administered=u.medication_administered,
                concern_flag=u.concern_flag,
                readiness_recommendation=u.readiness_recommendation,
                author_name=u.author.full_name if u.author else None,
            )
        )
    return results


# ============================================================================
# NGO FOSTER MANAGEMENT ENDPOINTS (Mounted at /api/v1/ngo/foster)
# ============================================================================

ngo_router = APIRouter()

@ngo_router.get("/homes", response_model=List[FosterHomePrivateResponse])
def list_ngo_foster_homes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in [UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    query = db.query(FosterHome)
    if current_user.role == UserRole.NGO_ADMIN:
        if not current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="NGO Admin has no organization associated")
        # Managed homes for this organization or independent available homes
        query = query.filter(
            (FosterHome.organization_id == current_user.organization_id) |
            (FosterHome.organization_id.is_(None))
        )

    homes = query.all()
    results = []
    for h in homes:
        results.append(
            FosterHomePrivateResponse(
                id=h.id,
                caregiver_id=h.caregiver_id,
                organization_id=h.organization_id,
                locality=h.locality,
                latitude=h.latitude,
                longitude=h.longitude,
                capacity=h.capacity,
                current_occupancy=h.current_occupancy,
                accepted_species=h.accepted_species,
                maximum_animal_size=h.maximum_animal_size,
                medical_care_supported=h.medical_care_supported,
                availability_status=h.availability_status,
                verified=h.verified,
                verified_at=h.verified_at,
                verified_by_user_id=h.verified_by_user_id,
                caregiver_name=h.caregiver.full_name if h.caregiver else None,
                caregiver_phone=h.caregiver.phone if h.caregiver else None,
                caregiver_email=h.caregiver.email if h.caregiver else None,
                created_at=h.created_at,
            )
        )
    return results


@ngo_router.get("/homes/{home_id}", response_model=FosterHomePrivateResponse)
def get_ngo_foster_home_detail(
    home_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in [UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    home = db.query(FosterHome).filter(FosterHome.id == home_id).first()
    if not home:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster home not found")

    if current_user.role == UserRole.NGO_ADMIN:
        if not current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization associated")
        if home.organization_id is not None and home.organization_id != current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")

    return FosterHomePrivateResponse(
        id=home.id,
        caregiver_id=home.caregiver_id,
        organization_id=home.organization_id,
        locality=home.locality,
        latitude=home.latitude,
        longitude=home.longitude,
        capacity=home.capacity,
        current_occupancy=home.current_occupancy,
        accepted_species=home.accepted_species,
        maximum_animal_size=home.maximum_animal_size,
        medical_care_supported=home.medical_care_supported,
        availability_status=home.availability_status,
        verified=home.verified,
        verified_at=home.verified_at,
        verified_by_user_id=home.verified_by_user_id,
        caregiver_name=home.caregiver.full_name if home.caregiver else None,
        caregiver_phone=home.caregiver.phone if home.caregiver else None,
        caregiver_email=home.caregiver.email if home.caregiver else None,
        created_at=home.created_at,
    )


@ngo_router.post("/homes/{home_id}/verify", response_model=FosterHomePrivateResponse)
def verify_foster_home(
    home_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in [UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    home = db.query(FosterHome).filter(FosterHome.id == home_id).first()
    if not home:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster home not found")

    if current_user.role == UserRole.NGO_ADMIN:
        if not current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization")
        # Associate with organization if independent
        if home.organization_id is None:
            home.organization_id = current_user.organization_id
        elif home.organization_id != current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot verify home of another organization")

    home.verified = True
    home.verified_at = datetime.utcnow()
    home.verified_by_user_id = current_user.id
    home.updated_at = datetime.utcnow()

    audit = AuditLog(
        actor_id=current_user.id,
        action="FOSTER_HOME_VERIFIED",
        entity="foster_home",
        entity_id=home.id,
        new_value={"verified": True, "organization_id": str(home.organization_id)},
        timestamp=datetime.utcnow(),
    )
    db.add(audit)
    db.commit()
    db.refresh(home)

    return FosterHomePrivateResponse(
        id=home.id,
        caregiver_id=home.caregiver_id,
        organization_id=home.organization_id,
        locality=home.locality,
        latitude=home.latitude,
        longitude=home.longitude,
        capacity=home.capacity,
        current_occupancy=home.current_occupancy,
        accepted_species=home.accepted_species,
        maximum_animal_size=home.maximum_animal_size,
        medical_care_supported=home.medical_care_supported,
        availability_status=home.availability_status,
        verified=home.verified,
        verified_at=home.verified_at,
        verified_by_user_id=home.verified_by_user_id,
        caregiver_name=home.caregiver.full_name if home.caregiver else None,
        caregiver_phone=home.caregiver.phone if home.caregiver else None,
        caregiver_email=home.caregiver.email if home.caregiver else None,
        created_at=home.created_at,
    )


@ngo_router.post("/homes/{home_id}/unverify", response_model=FosterHomePrivateResponse)
def unverify_foster_home(
    home_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in [UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    home = db.query(FosterHome).filter(FosterHome.id == home_id).first()
    if not home:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster home not found")

    if current_user.role == UserRole.NGO_ADMIN:
        if not current_user.organization_id or home.organization_id != current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")

    home.verified = False
    home.verified_at = None
    home.verified_by_user_id = None
    home.updated_at = datetime.utcnow()

    audit = AuditLog(
        actor_id=current_user.id,
        action="FOSTER_HOME_UNVERIFIED",
        entity="foster_home",
        entity_id=home.id,
        new_value={"verified": False},
        timestamp=datetime.utcnow(),
    )
    db.add(audit)
    db.commit()
    db.refresh(home)

    return FosterHomePrivateResponse(
        id=home.id,
        caregiver_id=home.caregiver_id,
        organization_id=home.organization_id,
        locality=home.locality,
        latitude=home.latitude,
        longitude=home.longitude,
        capacity=home.capacity,
        current_occupancy=home.current_occupancy,
        accepted_species=home.accepted_species,
        maximum_animal_size=home.maximum_animal_size,
        medical_care_supported=home.medical_care_supported,
        availability_status=home.availability_status,
        verified=home.verified,
        verified_at=home.verified_at,
        verified_by_user_id=home.verified_by_user_id,
        caregiver_name=home.caregiver.full_name if home.caregiver else None,
        caregiver_phone=home.caregiver.phone if home.caregiver else None,
        caregiver_email=home.caregiver.email if home.caregiver else None,
        created_at=home.created_at,
    )


@ngo_router.post("/matches", response_model=List[FosterMatchCandidate])
def find_foster_matches(
    payload: FosterMatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return FosterService.match_foster_homes(
        db=db,
        current_user=current_user,
        case_id=payload.case_id,
    )


@ngo_router.post("/assignments", response_model=FosterAssignmentResponse)
def create_foster_assignment(
    payload: FosterAssignmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = FosterService.create_offer(
        db=db,
        current_user=current_user,
        case_id=payload.rescue_case_id,
        foster_home_id=payload.foster_home_id,
        expected_end_date=payload.expected_end_date,
        notes=payload.notes,
    )
    return FosterAssignmentResponse(
        id=assignment.id,
        animal_id=assignment.animal_id,
        rescue_case_id=assignment.rescue_case_id,
        foster_home_id=assignment.foster_home_id,
        start_date=assignment.start_date,
        expected_end_date=assignment.expected_end_date,
        actual_end_date=assignment.actual_end_date,
        status=assignment.status,
        notes=assignment.notes,
        created_at=getattr(assignment, "created_at", None),
    )


@ngo_router.post("/assignments/{assignment_id}/complete", response_model=FosterAssignmentResponse)
def complete_foster_assignment(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = FosterService.end_assignment(
        db=db,
        current_user=current_user,
        assignment_id=assignment_id,
        new_status=FosterAssignmentStatus.COMPLETED.value,
    )
    return FosterAssignmentResponse(
        id=assignment.id,
        animal_id=assignment.animal_id,
        rescue_case_id=assignment.rescue_case_id,
        foster_home_id=assignment.foster_home_id,
        start_date=assignment.start_date,
        expected_end_date=assignment.expected_end_date,
        actual_end_date=assignment.actual_end_date,
        status=assignment.status,
        notes=assignment.notes,
        created_at=getattr(assignment, "created_at", None),
    )


@ngo_router.post("/assignments/{assignment_id}/cancel", response_model=FosterAssignmentResponse)
def cancel_foster_assignment(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = FosterService.end_assignment(
        db=db,
        current_user=current_user,
        assignment_id=assignment_id,
        new_status=FosterAssignmentStatus.CANCELLED.value,
    )
    return FosterAssignmentResponse(
        id=assignment.id,
        animal_id=assignment.animal_id,
        rescue_case_id=assignment.rescue_case_id,
        foster_home_id=assignment.foster_home_id,
        start_date=assignment.start_date,
        expected_end_date=assignment.expected_end_date,
        actual_end_date=assignment.actual_end_date,
        status=assignment.status,
        notes=assignment.notes,
        created_at=getattr(assignment, "created_at", None),
    )

