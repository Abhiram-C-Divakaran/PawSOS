from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from app.models.rescue_case import RescueCase
from app.models.rescue_status_history import RescueStatusHistory
from app.models.animal_image import AnimalImage
from app.models.user import User
from app.core.constants import RescueStatus, UserRole, ALLOWED_STATUS_TRANSITIONS, STATUS_ROLE_PERMISSIONS
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.schemas.rescue import RescueCreate
from app.services.triage_service import TriageService

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
            "breathing_difficulty": case_in.breathing_difficulty
        })

        db_case = RescueCase(
            case_number=case_number,
            reporter_id=reporter_id,
            species=case_in.species,
            description=case_in.description,
            latitude=case_in.latitude,
            longitude=case_in.longitude,
            address_text=case_in.address_text,
            bleeding=case_in.bleeding,
            can_walk=case_in.can_walk,
            conscious=case_in.conscious,
            vehicle_accident=case_in.vehicle_accident,
            breathing_difficulty=case_in.breathing_difficulty,
            triage_score=triage_result["score"],
            triage_priority=triage_result["priority"],
            triage_reason=", ".join(triage_result["reasons"]),
            status=RescueStatus.TRIAGED # Progresses from REPORTED to TRIAGED on submission
        )
        db.add(db_case)
        db.commit()
        db.refresh(db_case)

        # Record images if provided
        if case_in.image_url:
            img = AnimalImage(
                rescue_case_id=db_case.id,
                image_url=case_in.image_url,
                image_type="REPORT",
                uploaded_by=reporter_id
            )
            db.add(img)

        # Log status history
        history1 = RescueStatusHistory(
            rescue_case_id=db_case.id,
            new_status=RescueStatus.REPORTED,
            changed_by=reporter_id,
            notes="Case submitted by citizen"
        )
        history2 = RescueStatusHistory(
            rescue_case_id=db_case.id,
            previous_status=RescueStatus.REPORTED,
            new_status=RescueStatus.TRIAGED,
            notes="Auto-triaged based on reported condition"
        )
        db.add_all([history1, history2])
        db.commit()
        db.refresh(db_case)

        return db_case

    @staticmethod
    def update_status(
        db: Session,
        rescue_case: RescueCase,
        new_status: RescueStatus,
        user_id: uuid.UUID,
        notes: str = None,
        veterinary_facility_id: uuid.UUID = None
    ) -> RescueCase:
        previous_status = rescue_case.status

        # 1. Permission Verification
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
            if new_status == RescueStatus.CANCELLED and previous_status not in [RescueStatus.REPORTED, RescueStatus.TRIAGED]:
                raise ConflictException("Cannot cancel a rescue once a responder has been assigned.")

        # 2. State Machine Transition Verification
        allowed_targets = ALLOWED_STATUS_TRANSITIONS.get(previous_status, [])
        if new_status not in allowed_targets:
            raise ConflictException(
                f"Invalid status transition from '{previous_status.value}' to '{new_status.value}'."
            )

        # Update case
        rescue_case.status = new_status
        if veterinary_facility_id:
            rescue_case.veterinary_facility_id = veterinary_facility_id

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
            notes=notes
        )
        db.add(history)
        db.commit()

        return rescue_case
