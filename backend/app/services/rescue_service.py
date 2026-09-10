from sqlalchemy.orm import Session
from app.models.rescue_case import RescueCase
from app.models.rescue_status_history import RescueStatusHistory
from app.core.constants import RescueStatus
from app.schemas.rescue import RescueCreate
from app.services.triage_service import TriageService
import uuid

class RescueService:
    @staticmethod
    def create_case(db: Session, reporter_id: uuid.UUID, case_in: RescueCreate) -> RescueCase:
        # Generate case number
        case_number = f"PR-{uuid.uuid4().hex[:6].upper()}"
        
        # Run triage
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
            status=RescueStatus.TRIAGED # Progresses from REPORTED to TRIAGED instantly due to auto-triage
        )
        db.add(db_case)
        db.commit()
        db.refresh(db_case)

        # Log history
        history1 = RescueStatusHistory(rescue_case_id=db_case.id, new_status=RescueStatus.REPORTED, changed_by=reporter_id)
        history2 = RescueStatusHistory(rescue_case_id=db_case.id, previous_status=RescueStatus.REPORTED, new_status=RescueStatus.TRIAGED, notes="Auto-triaged by system")
        db.add_all([history1, history2])
        db.commit()

        return db_case

    @staticmethod
    def update_status(db: Session, rescue_case: RescueCase, new_status: RescueStatus, user_id: uuid.UUID, notes: str = None) -> RescueCase:
        previous_status = rescue_case.status
        rescue_case.status = new_status
        db.commit()
        db.refresh(rescue_case)

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
