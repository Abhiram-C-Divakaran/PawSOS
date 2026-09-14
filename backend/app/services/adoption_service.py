import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.models.rescue_case import RescueCase
from app.models.animal import Animal
from app.models.adoption_listing import AdoptionListing
from app.models.adoption_application import AdoptionApplication
from app.models.adoption_visit import AdoptionVisit
from app.models.foster_assignment import FosterAssignment
from app.models.foster_home import FosterHome
from app.models.rescue_status_history import RescueStatusHistory
from app.models.audit_log import AuditLog
from app.core.constants import (
    UserRole,
    RescueStatus,
    AdoptionListingStatus,
    AdoptionApplicationStatus,
    AdoptionVisitStatus,
    FosterAssignmentStatus,
    FosterHomeAvailability,
)
from app.services.notification_service import NotificationService
from app.schemas.adoption import AdoptionListingCreate, AdoptionApplicationCreate

class AdoptionService:

    @staticmethod
    def create_listing(
        db: Session,
        current_user: User,
        payload: AdoptionListingCreate,
    ) -> AdoptionListing:
        case = db.query(RescueCase).filter(RescueCase.id == payload.rescue_case_id).first()
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rescue case not found")

        # Tenant isolation
        if current_user.role == UserRole.NGO_ADMIN:
            if not current_user.organization_id or case.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
        elif current_user.role not in [UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to create adoption listings")

        # Eligibility check: case must be in READY_FOR_ADOPTION
        if case.status != RescueStatus.READY_FOR_ADOPTION.value and case.status != "READY_FOR_ADOPTION":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Animal must be in READY_FOR_ADOPTION status before creating an adoption listing (current: {case.status})",
            )

        # Check for existing active listing
        existing = (
            db.query(AdoptionListing)
            .filter(
                AdoptionListing.rescue_case_id == case.id,
                AdoptionListing.status.in_([
                    AdoptionListingStatus.DRAFT.value,
                    AdoptionListingStatus.PUBLISHED.value,
                    AdoptionListingStatus.PAUSED.value,
                ])
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An active adoption listing already exists for this case with status '{existing.status}'",
            )

        listing = AdoptionListing(
            animal_id=case.animal_id or uuid.uuid4(),
            rescue_case_id=case.id,
            organization_id=case.organization_id or current_user.organization_id,
            title=payload.title,
            public_description=payload.public_description,
            public_image_url=payload.public_image_url,
            status=AdoptionListingStatus.DRAFT.value,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(listing)

        audit = AuditLog(
            actor_id=current_user.id,
            action="ADOPTION_LISTING_CREATED",
            entity="adoption_listing",
            entity_id=listing.id,
            new_value={"case_id": str(case.id), "title": payload.title},
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        db.refresh(listing)
        return listing

    @staticmethod
    def publish_listing(
        db: Session,
        current_user: User,
        listing_id: uuid.UUID,
    ) -> AdoptionListing:
        listing = db.query(AdoptionListing).filter(AdoptionListing.id == listing_id).first()
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Adoption listing not found")

        # Tenancy
        if current_user.role == UserRole.NGO_ADMIN:
            if not current_user.organization_id or listing.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
        elif current_user.role not in [UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

        # Case must still be READY_FOR_ADOPTION
        case = db.query(RescueCase).filter(RescueCase.id == listing.rescue_case_id).first()
        if not case or case.status != RescueStatus.READY_FOR_ADOPTION.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Case is no longer in READY_FOR_ADOPTION status",
            )

        listing.status = AdoptionListingStatus.PUBLISHED.value
        listing.published_at = datetime.utcnow()
        listing.updated_at = datetime.utcnow()

        audit = AuditLog(
            actor_id=current_user.id,
            action="ADOPTION_LISTING_PUBLISHED",
            entity="adoption_listing",
            entity_id=listing.id,
            new_value={"status": "PUBLISHED"},
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        db.refresh(listing)
        return listing

    @staticmethod
    def pause_listing(
        db: Session,
        current_user: User,
        listing_id: uuid.UUID,
    ) -> AdoptionListing:
        listing = db.query(AdoptionListing).filter(AdoptionListing.id == listing_id).first()
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Adoption listing not found")

        if current_user.role == UserRole.NGO_ADMIN:
            if not current_user.organization_id or listing.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")

        listing.status = AdoptionListingStatus.PAUSED.value
        listing.updated_at = datetime.utcnow()

        audit = AuditLog(
            actor_id=current_user.id,
            action="ADOPTION_LISTING_PAUSED",
            entity="adoption_listing",
            entity_id=listing.id,
            new_value={"status": "PAUSED"},
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        db.refresh(listing)
        return listing

    @staticmethod
    def close_listing(
        db: Session,
        current_user: User,
        listing_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> AdoptionListing:
        listing = db.query(AdoptionListing).filter(AdoptionListing.id == listing_id).first()
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Adoption listing not found")

        if current_user.role == UserRole.NGO_ADMIN:
            if not current_user.organization_id or listing.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")

        listing.status = AdoptionListingStatus.CLOSED.value
        listing.closed_at = datetime.utcnow()
        listing.updated_at = datetime.utcnow()

        audit = AuditLog(
            actor_id=current_user.id,
            action="ADOPTION_LISTING_CLOSED",
            entity="adoption_listing",
            entity_id=listing.id,
            new_value={"status": "CLOSED", "reason": reason},
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        db.refresh(listing)
        return listing

    @staticmethod
    def submit_application(
        db: Session,
        current_user: User,
        listing_id: uuid.UUID,
        payload: AdoptionApplicationCreate,
    ) -> AdoptionApplication:
        listing = db.query(AdoptionListing).filter(AdoptionListing.id == listing_id).first()
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Adoption listing not found")

        if listing.status != AdoptionListingStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This animal is no longer available for adoption.",
            )

        case = db.query(RescueCase).filter(RescueCase.id == listing.rescue_case_id).first()
        if not case or case.status != RescueStatus.READY_FOR_ADOPTION.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This animal is no longer available for adoption.",
            )

        # Duplicate active application check
        existing = (
            db.query(AdoptionApplication)
            .filter(
                AdoptionApplication.listing_id == listing.id,
                AdoptionApplication.applicant_id == current_user.id,
                AdoptionApplication.status.in_([
                    AdoptionApplicationStatus.SUBMITTED.value,
                    AdoptionApplicationStatus.UNDER_REVIEW.value,
                    AdoptionApplicationStatus.VISIT_SCHEDULED.value,
                    AdoptionApplicationStatus.APPROVED.value,
                ]),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already submitted an active application for this animal.",
            )

        application = AdoptionApplication(
            listing_id=listing.id,
            applicant_id=current_user.id,
            status=AdoptionApplicationStatus.SUBMITTED.value,
            housing_type=payload.housing_type,
            owns_or_rents=payload.owns_or_rents,
            landlord_permission=payload.landlord_permission,
            household_size=payload.household_size,
            children_in_household=payload.children_in_household,
            existing_pets=payload.existing_pets,
            animal_experience=payload.animal_experience,
            reason_for_adoption=payload.reason_for_adoption,
            care_plan=payload.care_plan,
            submitted_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(application)

        audit = AuditLog(
            actor_id=current_user.id,
            action="ADOPTION_APPLICATION_SUBMITTED",
            entity="adoption_application",
            entity_id=application.id,
            new_value={"listing_id": str(listing.id)},
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        db.refresh(application)

        # Notify applicant
        NotificationService.notify_user(
            db=db,
            user_id=current_user.id,
            title="Adoption Application Received",
            message=f"Thank you for applying to adopt '{listing.title}'. Your application is now in queue.",
            notification_type="ADOPTION_APPLICATION_SUBMITTED",
            data={"application_id": str(application.id), "route": "/adoption-applications"},
        )

        return application

    @staticmethod
    def withdraw_application(
        db: Session,
        current_user: User,
        application_id: uuid.UUID,
    ) -> AdoptionApplication:
        application = db.query(AdoptionApplication).filter(AdoptionApplication.id == application_id).first()
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Adoption application not found")

        if application.applicant_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only withdraw your own applications")

        if application.status in [AdoptionApplicationStatus.APPROVED.value, AdoptionApplicationStatus.REJECTED.value]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot withdraw an application that has already been {application.status.lower()}",
            )

        application.status = AdoptionApplicationStatus.WITHDRAWN.value
        application.updated_at = datetime.utcnow()

        audit = AuditLog(
            actor_id=current_user.id,
            action="ADOPTION_APPLICATION_WITHDRAWN",
            entity="adoption_application",
            entity_id=application.id,
            new_value={"status": "WITHDRAWN"},
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        db.refresh(application)
        return application

    @staticmethod
    def schedule_visit(
        db: Session,
        current_user: User,
        application_id: uuid.UUID,
        scheduled_at: datetime,
        notes: Optional[str] = None,
    ) -> AdoptionVisit:
        application = db.query(AdoptionApplication).filter(AdoptionApplication.id == application_id).first()
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

        listing = db.query(AdoptionListing).filter(AdoptionListing.id == application.listing_id).first()
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

        # Tenancy
        if current_user.role == UserRole.NGO_ADMIN:
            if not current_user.organization_id or listing.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")

        visit = AdoptionVisit(
            application_id=application.id,
            scheduled_at=scheduled_at,
            status=AdoptionVisitStatus.SCHEDULED.value,
            notes=notes,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(visit)

        application.status = AdoptionApplicationStatus.VISIT_SCHEDULED.value
        application.updated_at = datetime.utcnow()

        audit = AuditLog(
            actor_id=current_user.id,
            action="ADOPTION_VISIT_SCHEDULED",
            entity="adoption_visit",
            entity_id=visit.id,
            new_value={"application_id": str(application.id), "scheduled_at": scheduled_at.isoformat()},
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        db.refresh(visit)

        NotificationService.notify_user(
            db=db,
            user_id=application.applicant_id,
            title="Adoption Visit Scheduled",
            message=f"An adoption visit has been scheduled for '{listing.title}'.",
            notification_type="ADOPTION_VISIT_SCHEDULED",
            data={"application_id": str(application.id), "route": "/adoption-applications"},
        )

        return visit

    @staticmethod
    def approve_application(
        db: Session,
        current_user: User,
        application_id: uuid.UUID,
        decision_notes: Optional[str] = None,
    ) -> AdoptionApplication:
        application = db.query(AdoptionApplication).filter(AdoptionApplication.id == application_id).first()
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

        # 1. Lock the adoption listing
        listing = (
            db.query(AdoptionListing)
            .filter(AdoptionListing.id == application.listing_id)
            .with_for_update()
            .first()
        )
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

        # Tenancy
        if current_user.role == UserRole.NGO_ADMIN:
            if not current_user.organization_id or listing.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
        elif current_user.role not in [UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

        # 2. Verify listing is still PUBLISHED
        if listing.status != AdoptionListingStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another applicant was approved before this action completed or listing is no longer published.",
            )

        # 3. Lock and verify rescue case is still READY_FOR_ADOPTION
        case = (
            db.query(RescueCase)
            .filter(RescueCase.id == listing.rescue_case_id)
            .with_for_update()
            .first()
        )
        if not case or case.status != RescueStatus.READY_FOR_ADOPTION.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This animal is no longer in READY_FOR_ADOPTION status (current: {case.status if case else 'None'}).",
            )

        # 4. Ensure no other application is already approved
        already_approved = (
            db.query(AdoptionApplication)
            .filter(
                AdoptionApplication.listing_id == listing.id,
                AdoptionApplication.status == AdoptionApplicationStatus.APPROVED.value,
            )
            .first()
        )
        if already_approved:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another applicant was approved before this action completed.",
            )

        # 5. Mark chosen application APPROVED
        application.status = AdoptionApplicationStatus.APPROVED.value
        application.reviewed_at = datetime.utcnow()
        application.reviewed_by_user_id = current_user.id
        application.decision_notes = decision_notes
        application.updated_at = datetime.utcnow()

        # 6. Reject other non-final applications
        pending_apps = (
            db.query(AdoptionApplication)
            .filter(
                AdoptionApplication.listing_id == listing.id,
                AdoptionApplication.id != application.id,
                AdoptionApplication.status.in_([
                    AdoptionApplicationStatus.SUBMITTED.value,
                    AdoptionApplicationStatus.UNDER_REVIEW.value,
                    AdoptionApplicationStatus.VISIT_SCHEDULED.value,
                ]),
            )
            .all()
        )
        for other_app in pending_apps:
            other_app.status = AdoptionApplicationStatus.REJECTED.value
            other_app.reviewed_at = datetime.utcnow()
            other_app.reviewed_by_user_id = current_user.id
            other_app.decision_notes = "Another applicant was approved for this animal."
            other_app.updated_at = datetime.utcnow()
            NotificationService.notify_user(
                db=db,
                user_id=other_app.applicant_id,
                title="Adoption Application Update",
                message=f"Another applicant was approved for '{listing.title}'. We appreciate your interest in adopting!",
                notification_type="ADOPTION_APPLICATION_REJECTED",
                data={"application_id": str(other_app.id), "route": "/adoption-applications"},
            )

        # 7. Close listing
        listing.status = AdoptionListingStatus.CLOSED.value
        listing.closed_at = datetime.utcnow()
        listing.updated_at = datetime.utcnow()

        # 8. Transition rescue case: READY_FOR_ADOPTION -> ADOPTED
        history = RescueStatusHistory(
            rescue_case_id=case.id,
            previous_status=case.status,
            new_status=RescueStatus.ADOPTED,
            changed_by=current_user.id,
            notes=f"Adoption finalized for application {application.id}",
        )
        db.add(history)
        case.status = RescueStatus.ADOPTED

        # 9. Complete active foster assignment if one exists
        active_foster_assign = (
            db.query(FosterAssignment)
            .filter(
                FosterAssignment.rescue_case_id == case.id,
                FosterAssignment.status == FosterAssignmentStatus.ACTIVE.value,
            )
            .first()
        )
        if active_foster_assign:
            foster_home = (
                db.query(FosterHome)
                .filter(FosterHome.id == active_foster_assign.foster_home_id)
                .with_for_update()
                .first()
            )
            active_foster_assign.status = FosterAssignmentStatus.COMPLETED.value
            active_foster_assign.actual_end_date = datetime.utcnow()
            if foster_home:
                foster_home.current_occupancy = max(0, foster_home.current_occupancy - 1)
                if foster_home.availability_status == FosterHomeAvailability.FULL.value:
                    foster_home.availability_status = FosterHomeAvailability.AVAILABLE.value

        # 10. Audit logs
        audit_app = AuditLog(
            actor_id=current_user.id,
            action="ADOPTION_APPLICATION_APPROVED",
            entity="adoption_application",
            entity_id=application.id,
            new_value={"listing_id": str(listing.id), "applicant_id": str(application.applicant_id)},
            timestamp=datetime.utcnow(),
        )
        db.add(audit_app)

        audit_case = AuditLog(
            actor_id=current_user.id,
            action="CASE_ADOPTED",
            entity="rescue_case",
            entity_id=case.id,
            new_value={"status": RescueStatus.ADOPTED.value, "application_id": str(application.id)},
            timestamp=datetime.utcnow(),
        )
        db.add(audit_case)
        db.commit()
        db.refresh(application)

        # 11. Notify successful applicant
        NotificationService.notify_user(
            db=db,
            user_id=application.applicant_id,
            title="Adoption Application Approved!",
            message=f"Congratulations! Your application to adopt '{listing.title}' has been approved.",
            notification_type="ADOPTION_APPLICATION_APPROVED",
            rescue_case_id=case.id,
            data={"application_id": str(application.id), "route": "/adoption-applications"},
        )

        return application

    @staticmethod
    def reject_application(
        db: Session,
        current_user: User,
        application_id: uuid.UUID,
        decision_notes: Optional[str] = None,
    ) -> AdoptionApplication:
        application = db.query(AdoptionApplication).filter(AdoptionApplication.id == application_id).first()
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

        listing = db.query(AdoptionListing).filter(AdoptionListing.id == application.listing_id).first()
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

        if current_user.role == UserRole.NGO_ADMIN:
            if not current_user.organization_id or listing.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
        elif current_user.role not in [UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

        application.status = AdoptionApplicationStatus.REJECTED.value
        application.reviewed_at = datetime.utcnow()
        application.reviewed_by_user_id = current_user.id
        application.decision_notes = decision_notes
        application.updated_at = datetime.utcnow()

        audit = AuditLog(
            actor_id=current_user.id,
            action="ADOPTION_APPLICATION_REJECTED",
            entity="adoption_application",
            entity_id=application.id,
            new_value={"decision_notes": decision_notes},
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        db.refresh(application)

        NotificationService.notify_user(
            db=db,
            user_id=application.applicant_id,
            title="Adoption Application Status",
            message=f"Your application for '{listing.title}' was reviewed and could not be approved at this time.",
            notification_type="ADOPTION_APPLICATION_REJECTED",
            data={"application_id": str(application.id), "route": "/adoption-applications"},
        )

        return application
