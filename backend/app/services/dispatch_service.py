import math
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Set, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import DBAPIError, OperationalError

from app.config import settings
from app.core.constants import (
    AssignmentStatus,
    RescuePriority,
    RescueStatus,
    RescuerAvailability,
    UserRole,
)
from app.core.exceptions import ConflictException, NotFoundException
from app.models.rescue_assignment import RescueAssignment
from app.models.rescue_case import RescueCase
from app.models.rescuer_profile import RescuerProfile
from app.models.user import User
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {
    RescuePriority.CRITICAL: 4,
    RescuePriority.URGENT: 3,
    RescuePriority.MODERATE: 2,
    RescuePriority.GENERAL: 1,
}

PRIORITY_MAX_OFFERS = {
    RescuePriority.CRITICAL: settings.DISPATCH_MAX_OFFERS_CRITICAL,
    RescuePriority.URGENT: settings.DISPATCH_MAX_OFFERS_URGENT,
    RescuePriority.MODERATE: settings.DISPATCH_MAX_OFFERS_MODERATE,
    RescuePriority.GENERAL: settings.DISPATCH_MAX_OFFERS_GENERAL,
}

EXPERIENCE_SCORES = {
    "expert": 100.0,
    "advanced": 85.0,
    "intermediate": 70.0,
    "beginner": 50.0,
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in kilometers."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


class DispatchService:
    @staticmethod
    def calculate_dispatch_score(
        distance_km: float, radius_km: float, profile: RescuerProfile
    ) -> float:
        """
        Calculate composite dispatch score from 0 to 100:
        - 40% Distance
        - 25% Availability/Readiness
        - 15% Experience
        - 10% Vehicle availability
        - 10% Reliability
        """
        # Distance score (100 = 0km, decreases linearly to 0 at or beyond current search radius)
        norm_dist = max(0.0, 1.0 - (distance_km / max(radius_km, 1.0)))
        dist_score = norm_dist * 100.0

        # Availability score
        avail_score = (
            100.0
            if profile.availability_status == RescuerAvailability.AVAILABLE
            else 0.0
        )

        # Experience score
        exp_level = (profile.experience_level or "intermediate").lower()
        exp_score = EXPERIENCE_SCORES.get(exp_level, 70.0)

        # Vehicle score
        veh_score = 100.0 if profile.vehicle_available else 40.0

        # Reliability score
        rel_score = min(100.0, max(0.0, float(profile.reliability_score or 100.0)))

        # Weighted sum
        composite = (
            settings.DISPATCH_WEIGHT_DISTANCE * dist_score
            + settings.DISPATCH_WEIGHT_AVAILABILITY * avail_score
            + settings.DISPATCH_WEIGHT_EXPERIENCE * exp_score
            + settings.DISPATCH_WEIGHT_VEHICLE * veh_score
            + settings.DISPATCH_WEIGHT_RELIABILITY * rel_score
        )

        return round(max(0.0, min(100.0, composite)), 1)

    @classmethod
    def find_eligible_responders(
        cls,
        db: Session,
        case: RescueCase,
        radius_km: float,
        excluded_rescuer_ids: Set[uuid.UUID],
    ) -> List[Tuple[User, RescuerProfile, float, float]]:
        """
        Find and score active, available responders within radius whose locations are not stale.
        Returns list of (User, RescuerProfile, distance_km, dispatch_score) sorted by score descending.
        """
        radius_km = float(radius_km)
        stale_threshold = datetime.utcnow() - timedelta(
            minutes=settings.RESPONDER_LOCATION_STALE_MINUTES
        )

        dialect_name = db.bind.dialect.name if db.bind else "sqlite"
        candidates = []

        if dialect_name == "postgresql":
            # Native PostGIS spatial query
            point_geom = func.ST_SetSRID(func.ST_MakePoint(case.longitude, case.latitude), 4326)
            rescuer_geom = func.coalesce(
                RescuerProfile.current_location,
                func.ST_SetSRID(func.ST_MakePoint(RescuerProfile.longitude, RescuerProfile.latitude), 4326),
            )
            query = (
                db.query(
                    User,
                    RescuerProfile,
                    (func.ST_Distance(rescuer_geom, point_geom) / 1000.0).label("dist_km"),
                )
                .join(RescuerProfile, RescuerProfile.user_id == User.id)
                .filter(
                    User.role == UserRole.RESCUER,
                    User.is_active == True,
                    RescuerProfile.availability_status == RescuerAvailability.AVAILABLE,
                    RescuerProfile.latitude.isnot(None),
                    RescuerProfile.longitude.isnot(None),
                    RescuerProfile.last_location_update >= stale_threshold,
                    func.ST_DWithin(rescuer_geom, point_geom, radius_km * 1000.0),
                )
                .all()
            )
            for user, profile, dist in query:
                if user.id not in excluded_rescuer_ids:
                    dist_km = round(float(dist), 2)
                    score = cls.calculate_dispatch_score(dist_km, radius_km, profile)
                    candidates.append((user, profile, dist_km, score))
        else:
            # Fallback for SQLite / tests
            query = (
                db.query(User, RescuerProfile)
                .join(RescuerProfile, RescuerProfile.user_id == User.id)
                .filter(
                    User.role == UserRole.RESCUER,
                    User.is_active == True,
                    RescuerProfile.availability_status == RescuerAvailability.AVAILABLE,
                    RescuerProfile.latitude.isnot(None),
                    RescuerProfile.longitude.isnot(None),
                    RescuerProfile.last_location_update >= stale_threshold,
                )
                .all()
            )
            for user, profile in query:
                if user.id in excluded_rescuer_ids:
                    continue
                dist_km = haversine_distance(
                    case.latitude, case.longitude, profile.latitude, profile.longitude
                )
                if dist_km <= radius_km:
                    score = cls.calculate_dispatch_score(dist_km, radius_km, profile)
                    candidates.append((user, profile, dist_km, score))

        # Sort: Highest dispatch score first, then closest distance
        candidates.sort(key=lambda item: (-item[3], item[2]))
        return candidates

    @classmethod
    def get_radius_levels(cls) -> List[float]:
        if isinstance(settings.DISPATCH_RADIUS_LEVELS, str):
            return [float(r.strip()) for r in settings.DISPATCH_RADIUS_LEVELS.split(",") if r.strip()]
        return [float(r) for r in settings.DISPATCH_RADIUS_LEVELS]

    @classmethod
    def dispatch_case(cls, db: Session, case_id: uuid.UUID, auto_escalate: bool = False) -> List[RescueAssignment]:
        """
        Execute automatic dispatch engine for a rescue case:
        1. Ensures case is in SEARCHING_RESPONDER status.
        2. Progressively searches expanding radii deterministically (Attempt 1 -> 5km, Attempt 2 -> 10km, etc.).
        3. Excludes previously contacted responders across all attempts.
        4. If all radii exhausted, transitions to UNRESOLVED with admin alert.
        5. Generates Dispatch Offers for top ranked responders up to priority limit.
        6. Sends real-time Push + In-App notifications.
        """
        case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
        if not case:
            logger.warning(f"Dispatch aborted: Rescue case {case_id} not found")
            return []

        if case.status not in [RescueStatus.TRIAGED, RescueStatus.SEARCHING_RESPONDER]:
            logger.info(f"Case {case_id} status is {case.status.value}, skipping dispatch")
            return []

        # If still TRIAGED, update to SEARCHING_RESPONDER
        if case.status == RescueStatus.TRIAGED:
            from app.services.rescue_service import RescueService
            RescueService.update_status(
                db,
                case,
                RescueStatus.SEARCHING_RESPONDER,
                case.reporter_id,
                notes="Automatic dispatch engine searching for responders",
            )

        radius_levels = cls.get_radius_levels()
        if not radius_levels:
            radius_levels = [5.0, 10.0, 20.0, 40.0]

        # Responders to exclude: already offered, pending, accepted, or rejected
        existing_assignments = (
            db.query(RescueAssignment)
            .filter(RescueAssignment.rescue_case_id == case.id)
            .all()
        )
        excluded_rescuer_ids: Set[uuid.UUID] = {
            a.rescuer_id
            for a in existing_assignments
            if a.assignment_status in [
                AssignmentStatus.PENDING,
                AssignmentStatus.REJECTED,
                AssignmentStatus.ACCEPTED,
                AssignmentStatus.EXPIRED,
            ]
        }

        max_offers = PRIORITY_MAX_OFFERS.get(
            case.triage_priority, settings.DISPATCH_MAX_OFFERS_GENERAL
        )

        # Initialize attempt and radius if not yet set
        if not case.dispatch_attempt or case.dispatch_attempt < 1:
            case.dispatch_attempt = 1
            case.dispatch_radius_km = radius_levels[0]

        logger.info(
            f"[EVENT: DISPATCH_STARTED] Case {case.case_number} (ID: {case.id}) | Attempt {case.dispatch_attempt} | Radius {case.dispatch_radius_km}km | Excluded: {len(excluded_rescuer_ids)}"
        )

        selected_candidates: List[Tuple[User, RescuerProfile, float, float]] = []

        if not auto_escalate:
            # Single-tier evaluation for current attempt (does not jump to UNRESOLVED in 0ms)
            attempt_idx = min(case.dispatch_attempt - 1, len(radius_levels) - 1)
            current_radius = radius_levels[attempt_idx]
            case.dispatch_radius_km = current_radius

            candidates = cls.find_eligible_responders(
                db=db,
                case=case,
                radius_km=current_radius,
                excluded_rescuer_ids=excluded_rescuer_ids,
            )
            if candidates:
                selected_candidates = candidates[:max_offers]
                logger.info(
                    f"[EVENT: RESPONDERS_FOUND] Found {len(selected_candidates)} candidates within {current_radius}km for case {case.case_number}"
                )
            else:
                logger.info(
                    f"No responders found within {current_radius}km for case {case.case_number}. Case remains searching; awaiting periodic worker."
                )
                case.last_dispatch_at = datetime.utcnow()
                db.commit()
                return []
        else:
            # Multi-tier escalation mode (used when explicitly testing exhaustion or by periodic worker)
            while case.dispatch_attempt <= len(radius_levels):
                current_radius = radius_levels[case.dispatch_attempt - 1]
                case.dispatch_radius_km = current_radius

                candidates = cls.find_eligible_responders(
                    db=db,
                    case=case,
                    radius_km=current_radius,
                    excluded_rescuer_ids=excluded_rescuer_ids,
                )

                if candidates:
                    selected_candidates = candidates[:max_offers]
                    logger.info(
                        f"[EVENT: RESPONDERS_FOUND] Found {len(selected_candidates)} candidates within {current_radius}km for case {case.case_number}"
                    )
                    break
                else:
                    logger.info(
                        f"No responders at {current_radius}km for case {case.case_number}. Advancing attempt {case.dispatch_attempt} -> {case.dispatch_attempt + 1}"
                    )
                    case.dispatch_attempt += 1
                    if case.dispatch_attempt <= len(radius_levels):
                        next_radius = radius_levels[case.dispatch_attempt - 1]
                        logger.info(
                            f"[EVENT: RADIUS_EXPANDED] Case {case.case_number} expanded to {next_radius}km (Attempt {case.dispatch_attempt})"
                        )

            # If all radius levels exhausted without candidates -> UNRESOLVED
            if not selected_candidates:
                logger.warning(
                    f"[EVENT: DISPATCH_FAILED] All {len(radius_levels)} radius levels exhausted for case {case.case_number}. Transitioning to UNRESOLVED."
                )
                from app.services.rescue_service import RescueService
                RescueService.update_status(
                    db=db,
                    rescue_case=case,
                    new_status=RescueStatus.UNRESOLVED,
                    user_id=None,
                    notes="Automatic dispatch exhausted all radii (5-40km) without finding available responders.",
                    system_update=True,
                )
                db.commit()

                # Alert NGO Admins and Super Admins
                cls._notify_dispatch_exhausted(db, case)
                return []

        # Create dispatch offers
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=settings.DISPATCH_OFFER_EXPIRY_SECONDS)
        case.last_dispatch_at = now
        created_offers: List[RescueAssignment] = []

        for user, profile, dist_km, score in selected_candidates:
            offer = RescueAssignment(
                rescue_case_id=case.id,
                rescuer_id=user.id,
                assigned_at=now,
                offered_at=now,
                expires_at=expires_at,
                assignment_status=AssignmentStatus.PENDING,
                distance_km=dist_km,
                dispatch_score=score,
            )
            db.add(offer)
            created_offers.append(offer)

        db.commit()

        logger.info(
            f"[EVENT: OFFERS_CREATED] Case {case.case_number} created {len(created_offers)} offers expiring in {settings.DISPATCH_OFFER_EXPIRY_SECONDS}s"
        )

        # Distribute Push Alerts + In-App Notifications
        for offer in created_offers:
            db.refresh(offer)
            payload = {
                "type": "DISPATCH_OFFER",
                "offer_id": str(offer.id),
                "case_id": str(case.id),
                "case_number": case.case_number,
                "priority": case.triage_priority.value,
                "species": case.species,
                "distance_km": offer.distance_km,
                "expires_at": expires_at.isoformat(),
                "route": f"/rescuer",
            }
            NotificationService.notify_user(
                db=db,
                user_id=offer.rescuer_id,
                title=f"🚨 New {case.triage_priority.value} Rescue Alert: {case.species}",
                message=f"Injured {case.species} reported {offer.distance_km}km away! Offer expires in {settings.DISPATCH_OFFER_EXPIRY_SECONDS}s.",
                notification_type="DISPATCH_OFFER",
                rescue_case_id=case.id,
                data=payload,
            )

        return created_offers

    @classmethod
    def _notify_dispatch_exhausted(cls, db: Session, case: RescueCase):
        """Send high-priority alerts to NGO Admins and Super Admins when dispatch fails."""
        from app.models.user import User
        query = db.query(User).filter(
            User.role.in_([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]),
            User.is_active == True,
        )
        if case.organization_id:
            query = query.filter(
                (User.organization_id == case.organization_id) | (User.role == UserRole.SUPER_ADMIN)
            )
        admins = query.all()
        admin_ids = [a.id for a in admins]

        if admin_ids:
            NotificationService.notify_users(
                db=db,
                user_ids=admin_ids,
                title=f"⚠️ Dispatch Failed: Case {case.case_number} Unresolved",
                message=f"No responder accepted within dispatch radius for case {case.case_number}. Manual intervention required.",
                notification_type="DISPATCH_FAILED",
                rescue_case_id=case.id,
                data={
                    "type": "DISPATCH_FAILED",
                    "case_id": str(case.id),
                    "case_number": case.case_number,
                    "route": f"/ngo/cases/{case.id}",
                },
            )

    @classmethod
    def process_dispatch_lifecycle(cls, db: Session) -> Tuple[int, int, int]:
        """
        Worker routine:
        1. Find PENDING offers where expires_at < now -> mark EXPIRED.
        2. Check affected cases.
        3. If no pending or accepted offers remain -> escalate to next radius level or transition to UNRESOLVED.
        Returns: (expired_count, escalated_count, failed_count)
        """
        now = datetime.utcnow()
        dialect_name = db.bind.dialect.name if db.bind else "sqlite"

        offer_query = db.query(RescueAssignment).filter(
            RescueAssignment.assignment_status == AssignmentStatus.PENDING,
            RescueAssignment.expires_at <= now,
        )
        if dialect_name == "postgresql":
            expired_offers = offer_query.with_for_update().all()
        else:
            expired_offers = offer_query.all()

        affected_case_ids: Set[uuid.UUID] = set()
        for offer in expired_offers:
            offer.assignment_status = AssignmentStatus.EXPIRED
            offer.expired_at = now
            affected_case_ids.add(offer.rescue_case_id)
            logger.info(
                f"[EVENT: OFFER_EXPIRED] Offer {offer.id} for case {offer.rescue_case_id} expired"
            )

        # Also find cases in SEARCHING_RESPONDER with no active offers whose attempt window expired
        expiry_threshold = now - timedelta(seconds=settings.DISPATCH_OFFER_EXPIRY_SECONDS)
        stale_searching_cases = (
            db.query(RescueCase.id)
            .filter(
                RescueCase.status == RescueStatus.SEARCHING_RESPONDER,
                (RescueCase.last_dispatch_at <= expiry_threshold) | (
                    (RescueCase.last_dispatch_at == None) & (RescueCase.created_at <= expiry_threshold)
                ),
            )
            .all()
        )
        for (c_id,) in stale_searching_cases:
            active_count = (
                db.query(RescueAssignment)
                .filter(
                    RescueAssignment.rescue_case_id == c_id,
                    RescueAssignment.assignment_status.in_([
                        AssignmentStatus.PENDING,
                        AssignmentStatus.ACCEPTED,
                    ]),
                )
                .count()
            )
            if active_count == 0:
                affected_case_ids.add(c_id)

        if not expired_offers and not affected_case_ids:
            return 0, 0, 0

        db.commit()

        # Notify affected responders
        for offer in expired_offers:
            NotificationService.notify_user(
                db=db,
                user_id=offer.rescuer_id,
                title="Rescue Offer Expired",
                message="A previous rescue offer has expired.",
                notification_type="DISPATCH_EXPIRED",
                rescue_case_id=offer.rescue_case_id,
            )

        radius_levels = cls.get_radius_levels()
        if not radius_levels:
            radius_levels = [5.0, 10.0, 20.0, 40.0]

        escalated_count = 0
        failed_count = 0

        # Attempt escalation for affected cases that still need a responder
        for case_id in affected_case_ids:
            case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
            if not case or case.status != RescueStatus.SEARCHING_RESPONDER:
                continue

            # Check if any active offers remain
            active_count = (
                db.query(RescueAssignment)
                .filter(
                    RescueAssignment.rescue_case_id == case.id,
                    RescueAssignment.assignment_status.in_([
                        AssignmentStatus.PENDING,
                        AssignmentStatus.ACCEPTED,
                    ]),
                )
                .count()
            )
            if active_count > 0:
                continue

            # Advance to next attempt
            case.dispatch_attempt = (case.dispatch_attempt or 1) + 1

            if case.dispatch_attempt > len(radius_levels):
                # All radii exhausted!
                from app.services.rescue_service import RescueService
                RescueService.update_status(
                    db=db,
                    rescue_case=case,
                    new_status=RescueStatus.UNRESOLVED,
                    user_id=None,
                    notes="Automatic dispatch exhausted all radii (5-40km) without acceptance.",
                    system_update=True,
                )
                db.commit()
                cls._notify_dispatch_exhausted(db, case)
                logger.warning(
                    f"[EVENT: DISPATCH_FAILED] Case {case.case_number} escalated to UNRESOLVED after all radius attempts"
                )
                failed_count += 1
            else:
                next_radius = radius_levels[case.dispatch_attempt - 1]
                case.dispatch_radius_km = next_radius
                case.last_dispatch_at = now
                logger.info(
                    f"[EVENT: RADIUS_EXPANDED] Case {case.case_number} advancing to {next_radius}km (Attempt {case.dispatch_attempt})"
                )
                db.commit()

                cls.dispatch_case(db, case.id)
                escalated_count += 1

        return len(expired_offers), escalated_count, failed_count

    @classmethod
    def expire_stale_offers(cls, db: Session) -> int:
        """Backward-compatible helper calling process_dispatch_lifecycle."""
        expired, _, _ = cls.process_dispatch_lifecycle(db)
        return expired

    @classmethod
    def accept_offer(
        cls, db: Session, offer_id: uuid.UUID, rescuer_id: uuid.UUID
    ) -> RescueAssignment:
        """
        Transactional acceptance with row-locking protection:
        - Winner claims assignment
        - Other offers are cancelled
        - Case transitions to RESPONDER_ASSIGNED
        - Citizen & NGO notified
        """
        try:
            # 1. Non-locking scalar lookup to determine the parent rescue case
            offer_lookup = (
                db.query(
                    RescueAssignment.id,
                    RescueAssignment.rescue_case_id,
                    RescueAssignment.assignment_status,
                    RescueAssignment.expires_at,
                )
                .filter(
                    RescueAssignment.id == offer_id,
                    RescueAssignment.rescuer_id == rescuer_id,
                )
                .first()
            )

            if not offer_lookup:
                raise NotFoundException("Dispatch offer not found for this rescuer")

            if offer_lookup.assignment_status != AssignmentStatus.PENDING:
                raise ConflictException(
                    f"Offer is no longer pending (current status: {offer_lookup.assignment_status.value})"
                )

            now = datetime.utcnow()
            if offer_lookup.expires_at and offer_lookup.expires_at < now:
                db.query(RescueAssignment).filter(RescueAssignment.id == offer_id).update({
                    "assignment_status": AssignmentStatus.EXPIRED,
                    "expired_at": now,
                })
                db.commit()
                raise ConflictException("Dispatch offer has expired")

            # 2. Concurrency row-locking on RescueCase FIRST to enforce a single global lock acquisition order.
            # with_for_update() with populate_existing() ensures fresh database state across concurrent transactions.
            case = (
                db.query(RescueCase)
                .filter(RescueCase.id == offer_lookup.rescue_case_id)
                .with_for_update()
                .populate_existing()
                .first()
            )

            if not case:
                raise NotFoundException("Rescue case not found")

            if case.status not in [RescueStatus.TRIAGED, RescueStatus.SEARCHING_RESPONDER]:
                db.query(RescueAssignment).filter(RescueAssignment.id == offer_id).update({
                    "assignment_status": AssignmentStatus.CANCELLED,
                })
                db.commit()
                raise ConflictException("This rescue has already been assigned to another responder or closed.")

            # 3. Retrieve the offer to mutate within the locked case critical section with populate_existing
            offer = (
                db.query(RescueAssignment)
                .filter(
                    RescueAssignment.id == offer_id,
                    RescueAssignment.rescuer_id == rescuer_id,
                )
                .with_for_update()
                .populate_existing()
                .first()
            )
            if not offer or offer.assignment_status != AssignmentStatus.PENDING:
                raise ConflictException("Offer is no longer available.")

            # Mark winning offer
            offer.assignment_status = AssignmentStatus.ACCEPTED
            offer.accepted_at = now

            # Cancel all other pending offers for this case
            other_offers = (
                db.query(RescueAssignment)
                .filter(
                    RescueAssignment.rescue_case_id == case.id,
                    RescueAssignment.id != offer.id,
                    RescueAssignment.assignment_status == AssignmentStatus.PENDING,
                )
                .all()
            )
            for other in other_offers:
                other.assignment_status = AssignmentStatus.CANCELLED
                NotificationService.notify_user(
                    db=db,
                    user_id=other.rescuer_id,
                    title="Rescue Assigned",
                    message=f"Case {case.case_number} was accepted by another responder.",
                    notification_type="DISPATCH_CANCELLED",
                    rescue_case_id=case.id,
                )

            # Update case status
            from app.services.rescue_service import RescueService
            rescuer = db.query(User).filter(User.id == rescuer_id).first()
            rescuer_name = rescuer.full_name if rescuer else "Responder"
            RescueService.update_status(
                db=db,
                rescue_case=case,
                new_status=RescueStatus.RESPONDER_ASSIGNED,
                user_id=rescuer_id,
                notes=f"Offer accepted by responder {rescuer_name}",
            )

            db.commit()
            db.refresh(offer)

            # Notify Citizen Reporter
            if case.reporter_id:
                NotificationService.notify_user(
                    db=db,
                    user_id=case.reporter_id,
                    title="🐾 Responder Assigned!",
                    message=f"{rescuer_name} has accepted your rescue report ({case.case_number}) and is preparing to respond.",
                    notification_type="RESPONDER_ASSIGNED",
                    rescue_case_id=case.id,
                    data={
                        "type": "RESPONDER_ASSIGNED",
                        "case_id": str(case.id),
                        "case_number": case.case_number,
                        "responder_name": rescuer_name,
                        "route": f"/cases/{case.id}",
                    },
                )

            logger.info(
                f"[EVENT: OFFER_ACCEPTED] Offer {offer.id} accepted by rescuer {rescuer_id} for case {case.case_number}"
            )

            return offer
        except (OperationalError, DBAPIError) as db_err:
            db.rollback()
            logger.warning(f"Database concurrency conflict during accept_offer: {db_err}")
            raise ConflictException("Concurrent assignment collision detected. Please try again.")

    @classmethod
    def reject_offer(
        cls,
        db: Session,
        offer_id: uuid.UUID,
        rescuer_id: uuid.UUID,
        reason: Optional[str] = "other",
    ) -> RescueAssignment:
        """Reject dispatch offer with specified reason and trigger next dispatch if needed."""
        dialect_name = db.bind.dialect.name if db.bind else "sqlite"
        query = db.query(RescueAssignment).filter(
            RescueAssignment.id == offer_id, RescueAssignment.rescuer_id == rescuer_id
        )
        if dialect_name == "postgresql":
            offer = query.with_for_update().first()
        else:
            offer = query.first()

        if not offer:
            raise NotFoundException("Dispatch offer not found for this rescuer")

        if offer.assignment_status != AssignmentStatus.PENDING:
            raise ConflictException("Only pending offers can be rejected")

        offer.assignment_status = AssignmentStatus.REJECTED
        offer.rejected_at = datetime.utcnow()
        offer.rejection_reason = reason
        db.commit()
        db.refresh(offer)

        logger.info(
            f"[EVENT: OFFER_REJECTED] Offer {offer.id} rejected by rescuer {rescuer_id} (Reason: {reason})"
        )

        # Check if case still has remaining pending offers
        remaining_pending = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.rescue_case_id == offer.rescue_case_id,
                RescueAssignment.assignment_status == AssignmentStatus.PENDING,
            )
            .count()
        )
        if remaining_pending == 0:
            cls.dispatch_case(db, offer.rescue_case_id)

        return offer

    @staticmethod
    def find_nearby_rescues(
        db: Session, lat: float, lng: float, radius_km: float = 10.0
    ) -> List[Tuple[RescueCase, float]]:
        """Geographic filtering for open rescue cases."""
        open_statuses = [RescueStatus.TRIAGED, RescueStatus.SEARCHING_RESPONDER]
        dialect_name = db.bind.dialect.name if db.bind else "sqlite"
        results: List[Tuple[RescueCase, float]] = []

        if dialect_name == "postgresql":
            point_geom = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
            query = (
                db.query(
                    RescueCase,
                    (func.ST_Distance(RescueCase.location, point_geom) / 1000.0).label("dist_km"),
                )
                .filter(
                    RescueCase.status.in_(open_statuses),
                    func.ST_DWithin(RescueCase.location, point_geom, radius_km * 1000.0),
                )
                .all()
            )
            for case, dist in query:
                results.append((case, round(float(dist), 2)))
        else:
            cases = db.query(RescueCase).filter(RescueCase.status.in_(open_statuses)).all()
            for case in cases:
                dist = haversine_distance(lat, lng, case.latitude, case.longitude)
                if dist <= radius_km:
                    results.append((case, dist))

        results.sort(
            key=lambda item: (
                -PRIORITY_ORDER.get(item[0].triage_priority, 0),
                item[1],
                item[0].created_at,
            )
        )
        return results

    @classmethod
    def handle_priority_escalation(
        cls, db: Session, case: RescueCase, new_priority: RescuePriority
    ) -> List[RescueAssignment]:
        """
        Adjust active dispatch when AI visual triage escalates case priority.
        If more offers are permitted by the higher priority, dispatches to additional
        eligible responders without duplicating existing or previously contacted responders.
        """
        if case.status != RescueStatus.SEARCHING_RESPONDER:
            return []

        pending_offers = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.rescue_case_id == case.id,
                RescueAssignment.assignment_status == AssignmentStatus.PENDING,
            )
            .all()
        )

        max_offers = PRIORITY_MAX_OFFERS.get(new_priority, 1)
        needed = max_offers - len(pending_offers)
        if needed <= 0:
            return []

        all_assignments = (
            db.query(RescueAssignment)
            .filter(RescueAssignment.rescue_case_id == case.id)
            .all()
        )
        excluded_ids = {a.rescuer_id for a in all_assignments}

        candidates = cls.find_eligible_responders(
            db=db,
            case=case,
            radius_km=case.dispatch_radius_km,
            excluded_rescuer_ids=excluded_ids,
        )

        if not candidates:
            return []

        selected = candidates[:needed]
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=settings.DISPATCH_OFFER_EXPIRY_SECONDS)
        new_offers: List[RescueAssignment] = []

        for user, profile, dist_km, score in selected:
            offer = RescueAssignment(
                rescue_case_id=case.id,
                rescuer_id=user.id,
                assigned_at=now,
                offered_at=now,
                expires_at=expires_at,
                assignment_status=AssignmentStatus.PENDING,
                distance_km=dist_km,
                dispatch_score=score,
            )
            db.add(offer)
            new_offers.append(offer)

        db.commit()

        for offer in new_offers:
            db.refresh(offer)
            payload = {
                "type": "DISPATCH_OFFER",
                "offer_id": str(offer.id),
                "case_id": str(case.id),
                "case_number": case.case_number,
                "priority": new_priority.value,
                "species": case.species,
                "distance_km": offer.distance_km,
                "expires_at": expires_at.isoformat(),
                "route": "/rescuer",
            }
            NotificationService.notify_user(
                db=db,
                user_id=offer.rescuer_id,
                title=f"🚨 Escalated {new_priority.value} Rescue Alert: {case.species}",
                message=f"Urgent {case.species} alert escalated to {new_priority.value}! Offer expires in {settings.DISPATCH_OFFER_EXPIRY_SECONDS}s.",
                notification_type="DISPATCH_OFFER",
                rescue_case_id=case.id,
                data=payload,
            )

        logger.info(
            f"[EVENT: DISPATCH_ESCALATED] Dispatched {len(new_offers)} additional offers for escalated case {case.case_number}"
        )
        return new_offers

