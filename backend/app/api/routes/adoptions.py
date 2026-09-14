import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.adoption_listing import AdoptionListing
from app.models.adoption_application import AdoptionApplication
from app.models.adoption_visit import AdoptionVisit
from app.models.rescue_case import RescueCase
from app.models.animal import Animal
from app.models.organization import Organization
from app.models.audit_log import AuditLog
from app.core.constants import (
    UserRole,
    AdoptionListingStatus,
    AdoptionApplicationStatus,
    AdoptionVisitStatus,
)
from app.api.dependencies import get_current_active_user as get_current_user
from app.services.adoption_service import AdoptionService
from app.schemas.adoption import (
    AdoptionListingCreate,
    AdoptionListingUpdate,
    AdoptionListingPublicResponse,
    AdoptionListingInternalResponse,
    AdoptionApplicationCreate,
    AdoptionApplicationApplicantResponse,
    AdoptionApplicationReviewerResponse,
    AdoptionVisitCreate,
    AdoptionVisitUpdate,
    AdoptionVisitResponse,
    AdoptionDecisionRequest,
)

router = APIRouter()

# ============================================================================
# PUBLIC ADOPTION CATALOG & CITIZEN APPLICATION
# ============================================================================

@router.get("", response_model=List[AdoptionListingPublicResponse])
@router.get("/", response_model=List[AdoptionListingPublicResponse])
def browse_adoption_listings(
    species: Optional[str] = None,
    organization_id: Optional[uuid.UUID] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = (
        db.query(AdoptionListing)
        .filter(AdoptionListing.status == AdoptionListingStatus.PUBLISHED.value)
    )

    if organization_id:
        query = query.filter(AdoptionListing.organization_id == organization_id)

    if species:
        query = query.join(Animal, AdoptionListing.animal_id == Animal.id).filter(
            Animal.species.ilike(f"%{species}%")
        )

    listings = query.order_by(AdoptionListing.published_at.desc()).offset(offset).limit(limit).all()

    results = []
    for l in listings:
        animal = l.animal
        org = l.organization
        results.append(
            AdoptionListingPublicResponse(
                id=l.id,
                title=l.title,
                public_description=l.public_description,
                public_image_url=l.public_image_url,
                status=l.status,
                published_at=l.published_at,
                species=animal.species if animal else None,
                sex=animal.sex if animal else None,
                approx_age=animal.approx_age if animal else None,
                colour=animal.colour if animal else None,
                identifying_marks=animal.identifying_marks if animal else None,
                sterilization_status=animal.sterilization_status if animal else None,
                vaccination_status=animal.vaccination_status if animal else None,
                organization_name=org.name if org else None,
                organization_operating_region=org.operating_region if org else None,
            )
        )
    return results


@router.get("/{listing_id}", response_model=AdoptionListingPublicResponse)
def get_adoption_listing_detail(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    listing = db.query(AdoptionListing).filter(AdoptionListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Adoption listing not found")

    if listing.status != AdoptionListingStatus.PUBLISHED.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This adoption listing is not currently active",
        )

    animal = listing.animal
    org = listing.organization
    return AdoptionListingPublicResponse(
        id=listing.id,
        title=listing.title,
        public_description=listing.public_description,
        public_image_url=listing.public_image_url,
        status=listing.status,
        published_at=listing.published_at,
        species=animal.species if animal else None,
        sex=animal.sex if animal else None,
        approx_age=animal.approx_age if animal else None,
        colour=animal.colour if animal else None,
        identifying_marks=animal.identifying_marks if animal else None,
        sterilization_status=animal.sterilization_status if animal else None,
        vaccination_status=animal.vaccination_status if animal else None,
        organization_name=org.name if org else None,
        organization_operating_region=org.operating_region if org else None,
    )


@router.post("/{listing_id}/apply", response_model=AdoptionApplicationApplicantResponse)
def apply_to_adopt(
    listing_id: uuid.UUID,
    payload: AdoptionApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = AdoptionService.submit_application(
        db=db,
        current_user=current_user,
        listing_id=listing_id,
        payload=payload,
    )
    listing = app.listing
    return AdoptionApplicationApplicantResponse(
        id=app.id,
        listing_id=app.listing_id,
        status=app.status,
        housing_type=app.housing_type,
        owns_or_rents=app.owns_or_rents,
        household_size=app.household_size,
        reason_for_adoption=app.reason_for_adoption,
        submitted_at=app.submitted_at,
        listing_title=listing.title if listing else None,
        animal_species=listing.animal.species if listing and listing.animal else None,
        public_image_url=listing.public_image_url if listing else None,
        organization_name=listing.organization.name if listing and listing.organization else None,
    )


# ============================================================================
# APPLICANT'S OWN APPLICATIONS
# ============================================================================

applicant_router = APIRouter()

@applicant_router.get("", response_model=List[AdoptionApplicationApplicantResponse])
@applicant_router.get("/", response_model=List[AdoptionApplicationApplicantResponse])
def get_my_adoption_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    apps = (
        db.query(AdoptionApplication)
        .filter(AdoptionApplication.applicant_id == current_user.id)
        .order_by(AdoptionApplication.submitted_at.desc())
        .all()
    )

    results = []
    for app in apps:
        listing = app.listing
        animal = listing.animal if listing else None
        org = listing.organization if listing else None
        latest_visit = app.visits[0] if app.visits else None
        visit_info = None
        if latest_visit:
            visit_info = {
                "id": str(latest_visit.id),
                "scheduled_at": latest_visit.scheduled_at.isoformat(),
                "status": latest_visit.status,
                "notes": latest_visit.notes,
            }

        results.append(
            AdoptionApplicationApplicantResponse(
                id=app.id,
                listing_id=app.listing_id,
                status=app.status,
                housing_type=app.housing_type,
                owns_or_rents=app.owns_or_rents,
                household_size=app.household_size,
                reason_for_adoption=app.reason_for_adoption,
                submitted_at=app.submitted_at,
                listing_title=listing.title if listing else None,
                animal_species=animal.species if animal else None,
                public_image_url=listing.public_image_url if listing else None,
                organization_name=org.name if org else None,
                visit_info=visit_info,
            )
        )
    return results


@applicant_router.get("/{application_id}", response_model=AdoptionApplicationApplicantResponse)
def get_my_adoption_application_detail(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = db.query(AdoptionApplication).filter(AdoptionApplication.id == application_id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    if app.applicant_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    listing = app.listing
    animal = listing.animal if listing else None
    org = listing.organization if listing else None
    latest_visit = app.visits[0] if app.visits else None
    visit_info = None
    if latest_visit:
        visit_info = {
            "id": str(latest_visit.id),
            "scheduled_at": latest_visit.scheduled_at.isoformat(),
            "status": latest_visit.status,
            "notes": latest_visit.notes,
        }

    return AdoptionApplicationApplicantResponse(
        id=app.id,
        listing_id=app.listing_id,
        status=app.status,
        housing_type=app.housing_type,
        owns_or_rents=app.owns_or_rents,
        household_size=app.household_size,
        reason_for_adoption=app.reason_for_adoption,
        submitted_at=app.submitted_at,
        listing_title=listing.title if listing else None,
        animal_species=animal.species if animal else None,
        public_image_url=listing.public_image_url if listing else None,
        organization_name=org.name if org else None,
        visit_info=visit_info,
    )


@applicant_router.post("/{application_id}/withdraw", response_model=AdoptionApplicationApplicantResponse)
def withdraw_my_adoption_application(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = AdoptionService.withdraw_application(
        db=db,
        current_user=current_user,
        application_id=application_id,
    )
    listing = app.listing
    return AdoptionApplicationApplicantResponse(
        id=app.id,
        listing_id=app.listing_id,
        status=app.status,
        housing_type=app.housing_type,
        owns_or_rents=app.owns_or_rents,
        household_size=app.household_size,
        reason_for_adoption=app.reason_for_adoption,
        submitted_at=app.submitted_at,
        listing_title=listing.title if listing else None,
        animal_species=listing.animal.species if listing and listing.animal else None,
        public_image_url=listing.public_image_url if listing else None,
        organization_name=listing.organization.name if listing and listing.organization else None,
    )


# ============================================================================
# NGO ADOPTION OPERATIONS ENDPOINTS
# ============================================================================

ngo_router = APIRouter()

@ngo_router.post("/listings", response_model=AdoptionListingInternalResponse)
def create_adoption_listing(
    payload: AdoptionListingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = AdoptionService.create_listing(
        db=db,
        current_user=current_user,
        payload=payload,
    )
    animal = listing.animal
    org = listing.organization
    case = listing.rescue_case
    return AdoptionListingInternalResponse(
        id=listing.id,
        animal_id=listing.animal_id,
        rescue_case_id=listing.rescue_case_id,
        organization_id=listing.organization_id,
        title=listing.title,
        public_description=listing.public_description,
        public_image_url=listing.public_image_url,
        status=listing.status,
        published_at=listing.published_at,
        species=animal.species if animal else None,
        sex=animal.sex if animal else None,
        approx_age=animal.approx_age if animal else None,
        colour=animal.colour if animal else None,
        identifying_marks=animal.identifying_marks if animal else None,
        sterilization_status=animal.sterilization_status if animal else None,
        vaccination_status=animal.vaccination_status if animal else None,
        organization_name=org.name if org else None,
        organization_operating_region=org.operating_region if org else None,
        case_number=case.case_number if case else None,
        created_by=listing.created_by,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
        applications_count=0,
        closed_at=listing.closed_at,
    )


@ngo_router.get("/listings", response_model=List[AdoptionListingInternalResponse])
def list_ngo_adoption_listings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in [UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    query = db.query(AdoptionListing)
    if current_user.role == UserRole.NGO_ADMIN:
        if not current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="NGO Admin has no organization associated")
        query = query.filter(AdoptionListing.organization_id == current_user.organization_id)

    listings = query.order_by(AdoptionListing.created_at.desc()).all()

    results = []
    for l in listings:
        animal = l.animal
        org = l.organization
        case = l.rescue_case
        apps_count = len(l.applications) if l.applications else 0
        results.append(
            AdoptionListingInternalResponse(
                id=l.id,
                animal_id=l.animal_id,
                rescue_case_id=l.rescue_case_id,
                organization_id=l.organization_id,
                title=l.title,
                public_description=l.public_description,
                public_image_url=l.public_image_url,
                status=l.status,
                published_at=l.published_at,
                species=animal.species if animal else None,
                sex=animal.sex if animal else None,
                approx_age=animal.approx_age if animal else None,
                colour=animal.colour if animal else None,
                identifying_marks=animal.identifying_marks if animal else None,
                sterilization_status=animal.sterilization_status if animal else None,
                vaccination_status=animal.vaccination_status if animal else None,
                organization_name=org.name if org else None,
                organization_operating_region=org.operating_region if org else None,
                case_number=case.case_number if case else None,
                created_by=l.created_by,
                created_at=l.created_at,
                updated_at=l.updated_at,
                applications_count=apps_count,
                closed_at=l.closed_at,
            )
        )
    return results


@ngo_router.post("/listings/{listing_id}/publish", response_model=AdoptionListingInternalResponse)
def publish_listing(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = AdoptionService.publish_listing(
        db=db,
        current_user=current_user,
        listing_id=listing_id,
    )
    animal = listing.animal
    org = listing.organization
    case = listing.rescue_case
    return AdoptionListingInternalResponse(
        id=listing.id,
        animal_id=listing.animal_id,
        rescue_case_id=listing.rescue_case_id,
        organization_id=listing.organization_id,
        title=listing.title,
        public_description=listing.public_description,
        public_image_url=listing.public_image_url,
        status=listing.status,
        published_at=listing.published_at,
        species=animal.species if animal else None,
        sex=animal.sex if animal else None,
        approx_age=animal.approx_age if animal else None,
        colour=animal.colour if animal else None,
        identifying_marks=animal.identifying_marks if animal else None,
        sterilization_status=animal.sterilization_status if animal else None,
        vaccination_status=animal.vaccination_status if animal else None,
        organization_name=org.name if org else None,
        organization_operating_region=org.operating_region if org else None,
        case_number=case.case_number if case else None,
        created_by=listing.created_by,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
        applications_count=len(listing.applications) if listing.applications else 0,
        closed_at=listing.closed_at,
    )


@ngo_router.post("/listings/{listing_id}/pause", response_model=AdoptionListingInternalResponse)
def pause_listing(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = AdoptionService.pause_listing(
        db=db,
        current_user=current_user,
        listing_id=listing_id,
    )
    return AdoptionListingInternalResponse(
        id=listing.id,
        animal_id=listing.animal_id,
        rescue_case_id=listing.rescue_case_id,
        organization_id=listing.organization_id,
        title=listing.title,
        public_description=listing.public_description,
        public_image_url=listing.public_image_url,
        status=listing.status,
        published_at=listing.published_at,
        created_by=listing.created_by,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
    )


@ngo_router.post("/listings/{listing_id}/close", response_model=AdoptionListingInternalResponse)
def close_listing(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = AdoptionService.close_listing(
        db=db,
        current_user=current_user,
        listing_id=listing_id,
    )
    return AdoptionListingInternalResponse(
        id=listing.id,
        animal_id=listing.animal_id,
        rescue_case_id=listing.rescue_case_id,
        organization_id=listing.organization_id,
        title=listing.title,
        public_description=listing.public_description,
        public_image_url=listing.public_image_url,
        status=listing.status,
        published_at=listing.published_at,
        created_by=listing.created_by,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
        closed_at=listing.closed_at,
    )


@ngo_router.get("/listings/{listing_id}/applications", response_model=List[AdoptionApplicationReviewerResponse])
def get_listing_applications(
    listing_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = db.query(AdoptionListing).filter(AdoptionListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    if current_user.role == UserRole.NGO_ADMIN:
        if not current_user.organization_id or listing.organization_id != current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    elif current_user.role not in [UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    apps = (
        db.query(AdoptionApplication)
        .filter(AdoptionApplication.listing_id == listing_id)
        .order_by(AdoptionApplication.submitted_at.desc())
        .all()
    )

    results = []
    for app in apps:
        applicant = app.applicant
        reviewer = app.reviewed_by
        visits_data = [
            {
                "id": str(v.id),
                "scheduled_at": v.scheduled_at.isoformat(),
                "status": v.status,
                "notes": v.notes,
            }
            for v in app.visits
        ]
        results.append(
            AdoptionApplicationReviewerResponse(
                id=app.id,
                listing_id=app.listing_id,
                applicant_id=app.applicant_id,
                applicant_name=applicant.full_name if applicant else None,
                applicant_phone=applicant.phone if applicant else None,
                applicant_email=applicant.email if applicant else None,
                status=app.status,
                housing_type=app.housing_type,
                owns_or_rents=app.owns_or_rents,
                landlord_permission=app.landlord_permission,
                household_size=app.household_size,
                children_in_household=app.children_in_household,
                existing_pets=app.existing_pets,
                animal_experience=app.animal_experience,
                reason_for_adoption=app.reason_for_adoption,
                care_plan=app.care_plan,
                submitted_at=app.submitted_at,
                reviewed_at=app.reviewed_at,
                reviewed_by_name=reviewer.full_name if reviewer else None,
                decision_notes=app.decision_notes,
                visits=visits_data,
                listing_title=listing.title,
                animal_species=listing.animal.species if listing.animal else None,
                case_number=listing.rescue_case.case_number if listing.rescue_case else None,
            )
        )
    return results


@ngo_router.post("/applications/{application_id}/review", response_model=AdoptionApplicationReviewerResponse)
def review_application(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = db.query(AdoptionApplication).filter(AdoptionApplication.id == application_id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    listing = app.listing
    if current_user.role == UserRole.NGO_ADMIN:
        if not current_user.organization_id or listing.organization_id != current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    elif current_user.role not in [UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    app.status = AdoptionApplicationStatus.UNDER_REVIEW.value
    app.reviewed_at = datetime.utcnow()
    app.reviewed_by_user_id = current_user.id
    app.updated_at = datetime.utcnow()

    audit = AuditLog(
        actor_id=current_user.id,
        action="ADOPTION_APPLICATION_REVIEW_STARTED",
        entity="adoption_application",
        entity_id=app.id,
        new_value={"status": "UNDER_REVIEW"},
        timestamp=datetime.utcnow(),
    )
    db.add(audit)
    db.commit()
    db.refresh(app)

    return AdoptionApplicationReviewerResponse(
        id=app.id,
        listing_id=app.listing_id,
        applicant_id=app.applicant_id,
        status=app.status,
        housing_type=app.housing_type,
        owns_or_rents=app.owns_or_rents,
        reason_for_adoption=app.reason_for_adoption,
        submitted_at=app.submitted_at,
        reviewed_at=app.reviewed_at,
        reviewed_by_name=current_user.full_name,
    )


@ngo_router.post("/applications/{application_id}/visits", response_model=AdoptionVisitResponse)
def schedule_adoption_visit(
    application_id: uuid.UUID,
    payload: AdoptionVisitCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = AdoptionService.schedule_visit(
        db=db,
        current_user=current_user,
        application_id=application_id,
        scheduled_at=payload.scheduled_at,
        notes=payload.notes,
    )
    return AdoptionVisitResponse(
        id=visit.id,
        application_id=visit.application_id,
        scheduled_at=visit.scheduled_at,
        status=visit.status,
        notes=visit.notes,
        created_by=visit.created_by,
        created_at=visit.created_at,
    )


@ngo_router.patch("/visits/{visit_id}", response_model=AdoptionVisitResponse)
def update_adoption_visit(
    visit_id: uuid.UUID,
    payload: AdoptionVisitUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = db.query(AdoptionVisit).filter(AdoptionVisit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")

    listing = visit.application.listing if visit.application else None
    if current_user.role == UserRole.NGO_ADMIN:
        if not listing or not current_user.organization_id or listing.organization_id != current_user.organization_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")

    if payload.status is not None:
        visit.status = payload.status
    if payload.scheduled_at is not None:
        visit.scheduled_at = payload.scheduled_at
    if payload.notes is not None:
        visit.notes = payload.notes

    visit.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(visit)
    return AdoptionVisitResponse(
        id=visit.id,
        application_id=visit.application_id,
        scheduled_at=visit.scheduled_at,
        status=visit.status,
        notes=visit.notes,
        created_by=visit.created_by,
        created_at=visit.created_at,
    )


@ngo_router.post("/applications/{application_id}/approve", response_model=AdoptionApplicationReviewerResponse)
def approve_adoption_application(
    application_id: uuid.UUID,
    payload: Optional[AdoptionDecisionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = AdoptionService.approve_application(
        db=db,
        current_user=current_user,
        application_id=application_id,
        decision_notes=payload.decision_notes if payload else None,
    )
    return AdoptionApplicationReviewerResponse(
        id=app.id,
        listing_id=app.listing_id,
        applicant_id=app.applicant_id,
        status=app.status,
        reason_for_adoption=app.reason_for_adoption,
        submitted_at=app.submitted_at,
        reviewed_at=app.reviewed_at,
        decision_notes=app.decision_notes,
    )


@ngo_router.post("/applications/{application_id}/reject", response_model=AdoptionApplicationReviewerResponse)
def reject_adoption_application(
    application_id: uuid.UUID,
    payload: Optional[AdoptionDecisionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = AdoptionService.reject_application(
        db=db,
        current_user=current_user,
        application_id=application_id,
        decision_notes=payload.decision_notes if payload else None,
    )
    return AdoptionApplicationReviewerResponse(
        id=app.id,
        listing_id=app.listing_id,
        applicant_id=app.applicant_id,
        status=app.status,
        reason_for_adoption=app.reason_for_adoption,
        submitted_at=app.submitted_at,
        reviewed_at=app.reviewed_at,
        decision_notes=app.decision_notes,
    )
