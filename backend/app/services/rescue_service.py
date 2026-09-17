from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from app.models.rescue_case import RescueCase
from app.models.rescue_status_history import RescueStatusHistory
from app.models.animal_image import AnimalImage
from app.models.rescue_assignment import RescueAssignment
from app.models.triage_assessment import TriageAssessment
from app.models.user import User
from app.core.constants import (
    RescueStatus,
    RescuePriority,
    UserRole,
    AssignmentStatus,
    ALLOWED_STATUS_TRANSITIONS,
    STATUS_ROLE_PERMISSIONS,
)
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.schemas.rescue import RescueCreate
from app.services.triage_service import TriageService
from app.services.notification_service import NotificationService
from app.config import settings


class RescueService:
    @staticmethod
    def create_case(db: Session, reporter_id: uuid.UUID, case_in: RescueCreate) -> RescueCase:
        # Generate unique case number
        case_number = f"PR-{uuid.uuid4().hex[:6].upper()}"

        # Run triage calculation
        triage_result = TriageService.calculate_triage({
            "bleeding": case_in.bleeding,
            "can_walk": case_in.can_walk,
            "conscious": case_in.conscious,
            "vehicle_accident": case_in.vehicle_accident,
            "breathing_difficulty": case_in.breathing_difficulty,
        })

        db_case = RescueCase(
            case_number=case_number,
            reporter_id=reporter_id,
            species=case_in.species,
            description=case_in.description,
            latitude=case_in.latitude,
            longitude=case_in.longitude,
            location=f"POINT({case_in.longitude} {case_in.latitude})",
            address_text=case_in.address_text,
            bleeding=case_in.bleeding,
            can_walk=case_in.can_walk,
            conscious=case_in.conscious,
            vehicle_accident=case_in.vehicle_accident,
            breathing_difficulty=case_in.breathing_difficulty,
            triage_score=triage_result["score"],
            triage_priority=triage_result["priority"],
            triage_reason=", ".join(triage_result["reasons"]),
            status=RescueStatus.TRIAGED,
        )
        db.add(db_case)
        db.commit()
        db.refresh(db_case)

        # Record images if provided
        img_id = None
        if case_in.image_url:
            from app.services.storage_service import normalize_image_key
            canonical_key = normalize_image_key(case_in.image_url) or case_in.image_url
            img = AnimalImage(
                rescue_case_id=db_case.id,
                image_url=canonical_key,
                image_type="REPORT",
                uploaded_by=reporter_id,
            )
            db.add(img)
            db.flush()
            img_id = img.id

        # Log status history
        history1 = RescueStatusHistory(
            rescue_case_id=db_case.id,
            new_status=RescueStatus.REPORTED,
            changed_by=reporter_id,
            notes="Case submitted by citizen",
        )
        history2 = RescueStatusHistory(
            rescue_case_id=db_case.id,
            previous_status=RescueStatus.REPORTED,
            new_status=RescueStatus.TRIAGED,
            notes="Auto-triaged based on reported condition",
        )
        history3 = RescueStatusHistory(
            rescue_case_id=db_case.id,
            previous_status=RescueStatus.TRIAGED,
            new_status=RescueStatus.SEARCHING_RESPONDER,
            notes="Automatic dispatch initiated",
        )
        db_case.status = RescueStatus.SEARCHING_RESPONDER
        db.add_all([history1, history2, history3])
        db.commit()
        db.refresh(db_case)

        # Notify Citizen reporter
        NotificationService.notify_user(
            db=db,
            user_id=reporter_id,
            title="🐾 Rescue Report Received",
            message=f"Your report for a {db_case.species} ({db_case.case_number}) has been triaged ({db_case.triage_priority.value}) and we are locating nearby responders.",
            notification_type="CASE_REPORTED",
            rescue_case_id=db_case.id,
            data={
                "type": "CASE_REPORTED",
                "case_id": str(db_case.id),
                "case_number": db_case.case_number,
                "priority": db_case.triage_priority.value,
                "route": f"/cases/{db_case.id}",
            },
        )

        # If CRITICAL, notify scoped NGO Admins and Super Admins immediately
        if db_case.triage_priority == RescuePriority.CRITICAL:
            recipients = NotificationService.get_critical_alert_recipients(
                db=db,
                organization_id=db_case.organization_id,
            )
            for admin in recipients:
                NotificationService.notify_user(
                    db=db,
                    user_id=admin.id,
                    title=f"🚨 CRITICAL Rescue Alert: {db_case.case_number}",
                    message=f"Critical case reported: {db_case.species} at {db_case.address_text or 'GPS Location'}. Automatic dispatch engaged.",
                    notification_type="CRITICAL_ALERT",
                    rescue_case_id=db_case.id,
                    data={"case_id": str(db_case.id), "priority": "CRITICAL"},
                )

        # Automatically trigger dispatch engine
        from app.services.dispatch_service import DispatchService
        DispatchService.dispatch_case(db, db_case.id)

        # Trigger asynchronous AI triage assessment if enabled and image attached
        if settings.AI_TRIAGE_ENABLED and settings.AI_TRIAGE_PROVIDER != "disabled" and img_id:
            assessment = TriageAssessment(
                rescue_case_id=db_case.id,
                animal_image_id=img_id,
                source="IMAGE_AI",
                status="PENDING",
                provider=settings.AI_TRIAGE_PROVIDER,
                model_name=settings.AI_TRIAGE_MODEL_NAME,
                model_version=settings.AI_TRIAGE_MODEL_VERSION,
                explanation="Visual assessment queued for execution.",
            )
            db.add(assessment)
            db.commit()
            db.refresh(assessment)

            try:
                from app.tasks.ai_triage_tasks import perform_ai_triage_task
                perform_ai_triage_task.delay(str(db_case.id), str(img_id))
            except Exception as task_err:
                import logging
                logging.getLogger(__name__).warning(
                    "[AI_TRIAGE_QUEUE] Failed to enqueue visual triage for case %s: %s",
                    db_case.case_number,
                    type(task_err).__name__,
                )
                assessment.status = "FAILED"
                assessment.sanitized_error_code = "QUEUE_ERROR"
                assessment.explanation = "Visual triage task could not be queued."
                assessment.completed_at = datetime.utcnow()
                db.commit()

        return db_case

    @staticmethod
    def update_status(
        db: Session,
        rescue_case: RescueCase,
        new_status: RescueStatus,
        user_id: Optional[uuid.UUID] = None,
        notes: str = None,
        veterinary_facility_id: uuid.UUID = None,
        system_update: bool = False,
    ) -> RescueCase:
        previous_status = rescue_case.status

        # 1. Permission Verification
        if not system_update:
            if not user_id:
                raise ForbiddenException("User ID is required for non-system status updates.")
            uid = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
            user = db.query(User).filter(User.id == uid).first()
            if not user:
                raise NotFoundException("User not found")

            allowed_for_role = STATUS_ROLE_PERMISSIONS.get(user.role, [])
            if new_status not in allowed_for_role:
                raise ForbiddenException(
                    f"Users with role '{user.role.value}' are not permitted to set status to '{new_status.value}'."
                )

            # Additional domain checks
            if user.role == UserRole.CITIZEN:
                if rescue_case.reporter_id != user.id:
                    raise ForbiddenException("Citizens can only manage their own reported rescues.")
                if new_status == RescueStatus.CANCELLED and previous_status not in [
                    RescueStatus.REPORTED,
                    RescueStatus.TRIAGED,
                ]:
                    raise ConflictException("Cannot cancel a rescue once a responder has been assigned.")

        # 2. State Machine Transition Verification
        allowed_targets = ALLOWED_STATUS_TRANSITIONS.get(previous_status, [])
        if new_status not in allowed_targets:
            raise ConflictException(
                f"Invalid status transition from '{previous_status.value}' to '{new_status.value}'."
            )

        # 3. Post-transition Role Scoping
        if not system_update and user:
            if user.role == UserRole.RESCUER and new_status != RescueStatus.CANCELLED:
                if previous_status in [
                    RescueStatus.RESPONDER_ASSIGNED,
                    RescueStatus.RESPONDER_EN_ROUTE,
                    RescueStatus.ANIMAL_LOCATED,
                    RescueStatus.RESCUED,
                    RescueStatus.TRANSPORTING,
                ]:
                    active_assignment = (
                        db.query(RescueAssignment)
                        .filter(
                            RescueAssignment.rescue_case_id == rescue_case.id,
                            RescueAssignment.rescuer_id == user.id,
                            RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED
                        )
                        .first()
                    )
                    if not active_assignment:
                        raise ForbiddenException("Only the assigned responder may update rescue progress.")

            if user.role == UserRole.VETERINARIAN:
                if not user.veterinary_facility_id:
                    raise ForbiddenException("Veterinarian is not associated with an authorized facility.")
                if rescue_case.veterinary_facility_id and rescue_case.veterinary_facility_id != user.veterinary_facility_id:
                    raise ForbiddenException("Veterinarians can only update cases assigned to their authorized facility.")

        # Update case
        rescue_case.status = new_status
        if veterinary_facility_id:
            rescue_case.veterinary_facility_id = veterinary_facility_id

        if new_status in [RescueStatus.READY_FOR_RELEASE, RescueStatus.RELEASED]:
            from app.models.adoption_listing import AdoptionListing
            from app.core.constants import AdoptionListingStatus
            active_listing = (
                db.query(AdoptionListing)
                .filter(
                    AdoptionListing.rescue_case_id == rescue_case.id,
                    AdoptionListing.status.in_([
                        AdoptionListingStatus.DRAFT.value,
                        AdoptionListingStatus.PUBLISHED.value,
                        AdoptionListingStatus.PAUSED.value,
                    ])
                )
                .first()
            )
            if active_listing:
                active_listing.status = AdoptionListingStatus.CLOSED.value
                active_listing.closed_at = datetime.utcnow()

        if new_status == RescueStatus.CLOSED:
            rescue_case.closed_at = datetime.utcnow()

        db.commit()
        db.refresh(rescue_case)

        # Log status transition history
        history = RescueStatusHistory(
            rescue_case_id=rescue_case.id,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=user_id,
            notes=notes,
        )
        db.add(history)
        db.commit()

        # Participant Notifications based on status update
        status_messages = {
            RescueStatus.RESPONDER_EN_ROUTE: ("Responder En Route", "A responder is en route to the animal's location."),
            RescueStatus.ANIMAL_LOCATED: ("Animal Located", "The responder has arrived and located the animal."),
            RescueStatus.RESCUED: ("Animal Rescued", "The animal has been secured safely."),
            RescueStatus.TRANSPORTING: ("Transporting to Facility", "The animal is being transported for veterinary care."),
            RescueStatus.AT_VETERINARY_FACILITY: ("Arrived at Clinic", "The animal has arrived safely at the veterinary facility."),
            RescueStatus.UNDER_TREATMENT: ("Treatment Started", "Veterinary medical treatment is currently underway."),
            RescueStatus.RECOVERING: ("Animal Recovering", "The animal is stable and recovering well under observation."),
            RescueStatus.READY_FOR_RELEASE: ("Ready for Release", "The animal has recovered and is approved for release."),
            RescueStatus.READY_FOR_ADOPTION: ("Ready for Adoption", "The animal is healthy and looking for a loving home."),
            RescueStatus.RELEASED: ("Animal Released", "The animal has been safely released to its natural habitat."),
            RescueStatus.ADOPTED: ("Animal Adopted", "The animal has found a permanent home!"),
            RescueStatus.CLOSED: ("Rescue Case Closed", "This rescue mission has been successfully completed."),
            RescueStatus.UNRESOLVED: ("Case Escalated", "This rescue case has been flagged as unresolved and requires NGO follow-up."),
        }

        if new_status in status_messages:
            title_prefix, body_text = status_messages[new_status]
            NotificationService.notify_rescue_participants(
                db=db,
                rescue_case_id=rescue_case.id,
                event_type=new_status.value,
                title=f"{title_prefix}: {rescue_case.case_number}",
                message=f"{body_text} (Case #{rescue_case.case_number})",
                extra_data={"status": new_status.value},
            )

        # If arriving at veterinary clinic, notify clinic veterinarians
        if new_status in [RescueStatus.AT_VETERINARY_FACILITY, RescueStatus.TRANSPORTING] and rescue_case.veterinary_facility_id:
            vet_users = (
                db.query(User)
                .filter(
                    User.veterinary_facility_id == rescue_case.veterinary_facility_id,
                    User.role == UserRole.VETERINARIAN,
                    User.is_active == True,
                )
                .all()
            )
            for vet in vet_users:
                NotificationService.notify_user(
                    db=db,
                    user_id=vet.id,
                    title="Incoming Rescue Patient",
                    message=f"Case #{rescue_case.case_number} ({rescue_case.species}) has been routed to your facility.",
                    notification_type="INCOMING_PATIENT",
                    rescue_case_id=rescue_case.id,
                    data={"route": "/veterinary"},
                )

        return rescue_case
