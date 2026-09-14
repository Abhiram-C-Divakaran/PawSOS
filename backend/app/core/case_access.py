"""Centralized Authorization Service for Rescue Cases & Evidence Media.

Enforces fail-closed access control policies for private case details and evidence images.
Separates responder discovery (e.g. /nearby) from private case/evidence access.

Policy Summary:
- SUPER_ADMIN / MUNICIPAL_ADMIN: Global administrative access.
- CITIZEN: Authorized only for cases they reported (case.reporter_id == user.id).
- RESCUER: Authorized only if they have an accepted assignment or an active (unexpired) dispatch offer.
          Case status being 'open' or 'reported' does NOT grant private case or evidence access.
- NGO_ADMIN: Fail-closed rule requiring user.organization_id == case.organization_id (both non-null).
            Unassigned cases (case.organization_id is None) do not grant private access to NGO admins.
- VETERINARIAN: Fail-closed rule requiring user.veterinary_facility_id == case.veterinary_facility_id
               (both non-null) AND case must be in an eligible veterinary lifecycle status.
- ALL OTHERS: Denied with HTTP 403 Forbidden.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.rescue_case import RescueCase
from app.models.rescue_assignment import RescueAssignment
from app.core.constants import UserRole, RescueStatus, AssignmentStatus
from app.core.exceptions import ForbiddenException

VETERINARY_LIFECYCLE_STATUSES = [
    RescueStatus.AT_VETERINARY_FACILITY,
    RescueStatus.UNDER_TREATMENT,
    RescueStatus.RECOVERING,
    RescueStatus.READY_FOR_RELEASE,
    RescueStatus.READY_FOR_ADOPTION,
    RescueStatus.RELEASED,
    RescueStatus.ADOPTED,
    RescueStatus.CLOSED,
]


def _is_unexpired(expires_at: Optional[datetime]) -> bool:
    """Check if offer expires_at timestamp is in the future.
    
    Database columns (RescueAssignment.expires_at) intentionally store naive UTC datetimes.
    To ensure compatibility with both naive column values and potential timezone-aware inputs:
    - If expires_at is timezone-aware, compare against datetime.now(timezone.utc).
    - If expires_at is naive, compare against datetime.utcnow().
    """
    if expires_at is None:
        return True
    if expires_at.tzinfo is not None:
        from datetime import timezone
        return expires_at > datetime.now(timezone.utc)
    return expires_at > datetime.utcnow()


def has_rescuer_case_relationship(case: RescueCase, user: User, db: Optional[Session] = None) -> bool:
    """Check if rescuer has an active relationship granting private case/evidence access.
    
    Valid relationships:
    1. Rescuer has accepted assignment for this case.
    2. Rescuer has an active, unexpired dispatch offer for this case.
    """
    now = datetime.utcnow()
    
    # Check preloaded assignments if available
    if hasattr(case, "assignments") and case.assignments is not None:
        for a in case.assignments:
            if a.rescuer_id == user.id:
                if a.assignment_status == AssignmentStatus.ACCEPTED:
                    return True
                if a.assignment_status == AssignmentStatus.PENDING:
                    if _is_unexpired(a.expires_at):
                        return True

    # Fallback to direct DB query if session is provided
    if db is not None:
        active = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.rescue_case_id == case.id,
                RescueAssignment.rescuer_id == user.id,
                (
                    (RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED) |
                    (
                        (RescueAssignment.assignment_status == AssignmentStatus.PENDING) &
                        ((RescueAssignment.expires_at.is_(None)) | (RescueAssignment.expires_at > now))
                    )
                )
            )
            .first()
        )
        if active is not None:
            return True

    return False


def has_foster_case_relationship(case: RescueCase, user: User, db: Optional[Session] = None) -> bool:
    """Check if foster caregiver has an active or offered assignment for this case."""
    if db is None:
        return False
    from app.models.foster_home import FosterHome
    from app.models.foster_assignment import FosterAssignment
    from app.core.constants import FosterAssignmentStatus

    active = (
        db.query(FosterAssignment)
        .join(FosterHome, FosterAssignment.foster_home_id == FosterHome.id)
        .filter(
            FosterAssignment.rescue_case_id == case.id,
            FosterHome.caregiver_id == user.id,
            FosterAssignment.status.in_([
                FosterAssignmentStatus.ACTIVE.value,
                FosterAssignmentStatus.OFFERED.value,
                "ACTIVE",
                "OFFERED",
            ]),
        )
        .first()
    )
    return active is not None


def verify_case_access(case: RescueCase, user: User, db: Optional[Session] = None) -> None:
    """Enforce strict, fail-closed authorization for private rescue case details and evidence images.
    
    Raises:
        ForbiddenException: If user is not authorized to access private case details or evidence.
    """
    # 1. Global administrative roles
    if user.role in [UserRole.SUPER_ADMIN, UserRole.MUNICIPAL_ADMIN]:
        return

    # 2. Citizen reporter ownership
    if user.role == UserRole.CITIZEN:
        if case.reporter_id != user.id:
            raise ForbiddenException("Citizens can only access their own reported rescue cases.")
        return

    # 3. Rescuer relationship check (fail-closed: status alone never grants access)
    if user.role == UserRole.RESCUER:
        if not has_rescuer_case_relationship(case, user, db):
            raise ForbiddenException(
                "Rescuers can only view cases assigned to them or with an active dispatch offer."
            )
        return

    # 4. NGO tenant isolation (fail-closed: both IDs must exist and match)
    if user.role == UserRole.NGO_ADMIN:
        if not user.organization_id:
            raise ForbiddenException("NGO Admin must be associated with an organization.")
        if not case.organization_id or case.organization_id != user.organization_id:
            raise ForbiddenException("Cross-tenant access forbidden: Case belongs to another organization.")
        return

    # 5. Veterinarian facility scoping (fail-closed: lifecycle status + matching non-null facility IDs)
    if user.role == UserRole.VETERINARIAN:
        if case.status not in VETERINARY_LIFECYCLE_STATUSES:
            raise ForbiddenException("Veterinarians can only view cases referred to veterinary care.")
        if not user.veterinary_facility_id:
            raise ForbiddenException("Veterinarian is not associated with an authorized facility.")
        if not case.veterinary_facility_id or case.veterinary_facility_id != user.veterinary_facility_id:
            raise ForbiddenException("Veterinarians can only view cases assigned to their authorized facility.")
        return

    # 6. Foster caregiver relationship check (fail-closed: active or offered assignment only)
    if user.role == UserRole.FOSTER:
        if not has_foster_case_relationship(case, user, db):
            raise ForbiddenException(
                "Foster caregivers can only access cases assigned or offered to them."
            )
        return

    # 7. Default deny for all other roles or unhandled states
    raise ForbiddenException("Access denied.")


def can_view_case_private_details(case: RescueCase, user: User, db: Optional[Session] = None) -> bool:
    """Predicate helper: returns True if user may view private case details, False otherwise."""
    try:
        verify_case_access(case, user, db)
        return True
    except ForbiddenException:
        return False


def can_access_case_evidence(case: RescueCase, user: User, db: Optional[Session] = None) -> bool:
    """Predicate helper: returns True if user may access private evidence media, False otherwise."""
    try:
        verify_case_access(case, user, db)
        return True
    except ForbiddenException:
        return False
