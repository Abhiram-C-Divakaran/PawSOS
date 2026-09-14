import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.models.rescue_case import RescueCase
from app.models.animal import Animal
from app.models.foster_home import FosterHome
from app.models.foster_assignment import FosterAssignment
from app.models.rescue_status_history import RescueStatusHistory
from app.models.audit_log import AuditLog
from app.core.constants import (
    UserRole,
    RescueStatus,
    FosterAssignmentStatus,
    FosterHomeAvailability,
)
from app.services.notification_service import NotificationService
from app.schemas.foster import FosterMatchCandidate

class FosterService:

    @staticmethod
    def match_foster_homes(
        db: Session,
        current_user: User,
        case_id: uuid.UUID,
        max_candidates: int = 10,
    ) -> List[FosterMatchCandidate]:
        case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rescue case not found")

        # Tenant isolation: NGO Admin can only match cases belonging to their org
        if current_user.role == UserRole.NGO_ADMIN:
            if not current_user.organization_id or case.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")

        animal = db.query(Animal).filter(Animal.id == case.animal_id).first() if case.animal_id else None
        target_species = (case.species or (animal.species if animal else "") or "Dog").lower()

        # Query eligible foster homes: verified, available, under capacity
        query = db.query(FosterHome).filter(
            FosterHome.verified == True,
            FosterHome.availability_status == FosterHomeAvailability.AVAILABLE.value,
            FosterHome.current_occupancy < FosterHome.capacity,
        )

        # NGO tenancy scoping: match homes belonging to this organization or independent homes
        if current_user.role == UserRole.NGO_ADMIN and current_user.organization_id:
            query = query.filter(
                (FosterHome.organization_id == current_user.organization_id) |
                (FosterHome.organization_id.is_(None))
            )

        homes = query.all()
        candidates: List[FosterMatchCandidate] = []

        for home in homes:
            reasons = []
            remaining_capacity = max(0, home.capacity - home.current_occupancy)

            # 1. Species compatibility
            home_species = (home.accepted_species or "Dog, Cat").lower()
            species_match = target_species in home_species or "all" in home_species
            if species_match:
                reasons.append(f"Accepts {target_species.capitalize()}")
            else:
                reasons.append(f"Preferred species does not list {target_species.capitalize()}")

            # 2. Medical care compatibility
            case_priority_val = (
                case.triage_priority.value
                if hasattr(case.triage_priority, "value")
                else str(case.triage_priority or "")
            )
            needs_medical = case_priority_val in ["CRITICAL", "URGENT"]
            medical_match = True
            if needs_medical and not home.medical_care_supported:
                medical_match = False
                reasons.append("Animal requires specialized medical care not supported by home")
            elif home.medical_care_supported:
                reasons.append("Medical care support verified")

            # 3. Size compatibility
            size_match = True
            reasons.append("Capacity verified")

            compatible = species_match and medical_match and (remaining_capacity > 0)

            # Deterministic scoring
            score = 50.0
            if species_match:
                score += 25.0
            if medical_match and home.medical_care_supported:
                score += 15.0
            score += min(10.0, remaining_capacity * 5.0)

            candidates.append(
                FosterMatchCandidate(
                    foster_home_id=home.id,
                    locality=home.locality or "Area Registered",
                    capacity=home.capacity,
                    current_occupancy=home.current_occupancy,
                    remaining_capacity=remaining_capacity,
                    verified=home.verified,
                    availability_status=home.availability_status,
                    compatible=compatible,
                    match_score=round(score, 1),
                    species_match=species_match,
                    medical_support_match=medical_match,
                    size_match=size_match,
                    match_reasons=reasons,
                )
            )

        candidates.sort(key=lambda c: (c.compatible, c.match_score), reverse=True)
        return candidates[:max_candidates]

    @staticmethod
    def create_offer(
        db: Session,
        current_user: User,
        case_id: uuid.UUID,
        foster_home_id: uuid.UUID,
        expected_end_date: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> FosterAssignment:
        case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rescue case not found")

        # Tenant isolation
        if current_user.role == UserRole.NGO_ADMIN:
            if not current_user.organization_id or case.organization_id != current_user.organization_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
        elif current_user.role not in [UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to create foster offers")

        foster_home = db.query(FosterHome).filter(FosterHome.id == foster_home_id).first()
        if not foster_home:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster home not found")

        if not foster_home.verified:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot offer assignment to unverified foster home")

        if foster_home.current_occupancy >= foster_home.capacity:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Foster home has reached capacity")

        # Ensure no other active or offered assignment exists for this case
        existing_active = (
            db.query(FosterAssignment)
            .filter(
                FosterAssignment.rescue_case_id == case.id,
                FosterAssignment.status.in_([FosterAssignmentStatus.ACTIVE.value, FosterAssignmentStatus.OFFERED.value]),
            )
            .first()
        )
        if existing_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Case already has a foster assignment with status {existing_active.status}",
            )

        assignment = FosterAssignment(
            animal_id=case.animal_id or uuid.uuid4(),
            rescue_case_id=case.id,
            foster_home_id=foster_home.id,
            status=FosterAssignmentStatus.OFFERED.value,
            expected_end_date=expected_end_date,
            notes=notes,
            created_at=datetime.utcnow(),
        )
        db.add(assignment)

        # Audit log
        audit = AuditLog(
            actor_id=current_user.id,
            action="FOSTER_OFFER_CREATED",
            entity="foster_assignment",
            entity_id=assignment.id,
            new_value={"case_id": str(case.id), "foster_home_id": str(foster_home.id)},
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        db.refresh(assignment)

        # Notify caregiver
        NotificationService.notify_user(
            db=db,
            user_id=foster_home.caregiver_id,
            title="New Foster Care Offer",
            message=f"You have received a foster offer for rescue case {case.case_number}.",
            notification_type="FOSTER_OFFER_NEW",
            rescue_case_id=case.id,
            data={"assignment_id": str(assignment.id), "route": "/foster"},
        )

        return assignment

    @staticmethod
    def accept_offer(db: Session, current_user: User, assignment_id: uuid.UUID) -> FosterAssignment:
        assignment = db.query(FosterAssignment).filter(FosterAssignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster assignment not found")

        foster_home = (
            db.query(FosterHome)
            .filter(FosterHome.id == assignment.foster_home_id)
            .with_for_update()
            .first()
        )
        if not foster_home:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster home not found")

        # Must be the assigned caregiver
        if foster_home.caregiver_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only assigned caregiver may accept foster offer")

        if assignment.status != FosterAssignmentStatus.OFFERED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Assignment cannot be accepted from current status '{assignment.status}'",
            )

        # Concurrency safety: check capacity with row lock
        if foster_home.current_occupancy >= foster_home.capacity or foster_home.availability_status != FosterHomeAvailability.AVAILABLE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This foster home has reached capacity or is no longer available",
            )

        # Activate assignment and increment occupancy atomically
        assignment.status = FosterAssignmentStatus.ACTIVE.value
        assignment.start_date = datetime.utcnow()
        foster_home.current_occupancy += 1
        if foster_home.current_occupancy >= foster_home.capacity:
            foster_home.availability_status = FosterHomeAvailability.FULL.value

        # Advance case status to FOSTER_CARE if appropriate
        if assignment.rescue_case_id:
            case = db.query(RescueCase).filter(RescueCase.id == assignment.rescue_case_id).first()
            if case and case.status in [RescueStatus.RECOVERING.value, "RECOVERING"]:
                history = RescueStatusHistory(
                    rescue_case_id=case.id,
                    previous_status=case.status,
                    new_status=RescueStatus.FOSTER_CARE,
                    changed_by=current_user.id,
                    notes=f"Animal placed in foster care with home {foster_home.id}",
                )
                db.add(history)
                case.status = RescueStatus.FOSTER_CARE

        audit = AuditLog(
            actor_id=current_user.id,
            action="FOSTER_OFFER_ACCEPTED",
            entity="foster_assignment",
            entity_id=assignment.id,
            new_value={"status": "ACTIVE", "occupancy": foster_home.current_occupancy},
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        db.refresh(assignment)

        return assignment

    @staticmethod
    def decline_offer(db: Session, current_user: User, assignment_id: uuid.UUID) -> FosterAssignment:
        assignment = db.query(FosterAssignment).filter(FosterAssignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster assignment not found")

        foster_home = db.query(FosterHome).filter(FosterHome.id == assignment.foster_home_id).first()
        if not foster_home:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster home not found")

        if foster_home.caregiver_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only assigned caregiver may decline foster offer")

        if assignment.status != FosterAssignmentStatus.OFFERED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Assignment cannot be declined from status '{assignment.status}'",
            )

        assignment.status = FosterAssignmentStatus.DECLINED.value

        audit = AuditLog(
            actor_id=current_user.id,
            action="FOSTER_OFFER_DECLINED",
            entity="foster_assignment",
            entity_id=assignment.id,
            new_value={"status": "DECLINED"},
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        db.refresh(assignment)
        return assignment

    @staticmethod
    def end_assignment(
        db: Session,
        current_user: User,
        assignment_id: uuid.UUID,
        new_status: str,  # COMPLETED or CANCELLED
        notes: Optional[str] = None,
    ) -> FosterAssignment:
        if new_status not in [FosterAssignmentStatus.COMPLETED.value, FosterAssignmentStatus.CANCELLED.value]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid termination status: {new_status}")

        assignment = db.query(FosterAssignment).filter(FosterAssignment.id == assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster assignment not found")

        foster_home = (
            db.query(FosterHome)
            .filter(FosterHome.id == assignment.foster_home_id)
            .with_for_update()
            .first()
        )
        if not foster_home:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Foster home not found")

        # Authorization: caregiver, managing NGO admin, or Super Admin
        is_caregiver = foster_home.caregiver_id == current_user.id
        is_managing_ngo = (
            current_user.role == UserRole.NGO_ADMIN and
            current_user.organization_id is not None and
            foster_home.organization_id == current_user.organization_id
        )
        is_admin = current_user.role in [UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]

        if not (is_caregiver or is_managing_ngo or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to end foster assignment")

        # Idempotency: if already in requested status, do not decrement again
        if assignment.status == new_status:
            return assignment

        was_active = assignment.status == FosterAssignmentStatus.ACTIVE.value

        assignment.status = new_status
        assignment.actual_end_date = datetime.utcnow()
        if notes:
            assignment.notes = f"{assignment.notes or ''}\n{notes}".strip()

        # If it was active, decrement occupancy exactly once
        if was_active:
            foster_home.current_occupancy = max(0, foster_home.current_occupancy - 1)
            if foster_home.availability_status == FosterHomeAvailability.FULL.value:
                foster_home.availability_status = FosterHomeAvailability.AVAILABLE.value

        audit = AuditLog(
            actor_id=current_user.id,
            action=f"FOSTER_ASSIGNMENT_{new_status}",
            entity="foster_assignment",
            entity_id=assignment.id,
            new_value={"status": new_status, "occupancy": foster_home.current_occupancy},
            timestamp=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        db.refresh(assignment)
        return assignment
