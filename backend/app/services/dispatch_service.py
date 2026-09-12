import math
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Set, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

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
            query = (
                db.query(
                    User,
                    RescuerProfile,
                    (func.ST_Distance(RescuerProfile.current_location, point_geom) / 1000.0).label("dist_km"),
                )
                .join(RescuerProfile, RescuerProfile.user_id == User.id)
                .filter(
                    User.role == UserRole.RESCUER,
                    User.is_active == True,
                    RescuerProfile.availability_status == RescuerAvailability.AVAILABLE,
                    RescuerProfile.latitude.isnot(None),
                    RescuerProfile.longitude.isnot(None),
                    RescuerProfile.last_location_update >= stale_threshold,
                    func.ST_DWithin(RescuerProfile.current_location, point_geom, radius_km * 1000.0),
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
    def dispatch_case(cls, db: Session, case_id: uuid.UUID) -> List[RescueAssignment]:
        """
        Execute automatic dispatch engine for a rescue case:
        1. Ensures case is in SEARCHING_RESPONDER status.
        2. Progressively searches expanding radii.
        3. Generates Dispatch Offers for top ranked responders up to priority limit.
        4. Sends real-time Push + In-App notifications.
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

        # Responders to exclude: already offered, or previously rejected
        existing_assignments = (
            db.query(RescueAssignment)
            .filter(RescueAssignment.rescue_case_id == case.id)
            .all()
        )
        excluded_rescuer_ids: Set[uuid.UUID] = {
            a.rescuer_id
            for a in existing_assignments
            if a.assignment_status in [AssignmentStatus.PENDING, AssignmentStatus.REJECTED, AssignmentStatus.ACCEPTED]
        }

        max_offers = PRIORITY_MAX_OFFERS.get(
            case.triage_priority, settings.DISPATCH_MAX_OFFERS_GENERAL
        )

        # Progressively expanding radii
        selected_candidates: List[Tuple[User, RescuerProfile, float, float]] = []
        radius_levels = (
            [float(r.strip()) for r in str(settings.DISPATCH_RADIUS_LEVELS).split(",") if r.strip()]
            if isinstance(settings.DISPATCH_RADIUS_LEVELS, str)
            else [float(r) for r in settings.DISPATCH_RADIUS_LEVELS]
        )
        for radius in radius_levels:
            candidates = cls.find_eligible_responders(
                db=db,
                case=case,
                radius_km=radius,
                excluded_rescuer_ids=excluded_rescuer_ids,
            )
            if candidates:
                selected_candidates = candidates[:max_offers]
                logger.info(
                    f"Found {len(selected_candidates)} candidates within {radius}km for case {case.case_number}"
                )
                break

        if not selected_candidates:
            max_rad = radius_levels[-1] if radius_levels else 40.0
            logger.info(
                f"No eligible responders found within max radius {max_rad}km for case {case.case_number}"
            )
            return []

        # Create dispatch offers
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=settings.DISPATCH_OFFER_EXPIRY_SECONDS)
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
    def expire_stale_offers(cls, db: Session) -> int:
        """
        Scan and expire offers past their expiry deadline.
        Triggers radius escalation for cases still needing responders.
        """
        now = datetime.utcnow()
        expired_offers = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.assignment_status == AssignmentStatus.PENDING,
                RescueAssignment.expires_at <= now,
            )
            .all()
        )

        if not expired_offers:
            return 0

        affected_case_ids = set()
        for offer in expired_offers:
            offer.assignment_status = AssignmentStatus.EXPIRED
            offer.expired_at = now
            affected_case_ids.add(offer.rescue_case_id)

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

        # Attempt escalation for cases with no active pending offers
        for case_id in affected_case_ids:
            remaining_pending = (
                db.query(RescueAssignment)
                .filter(
                    RescueAssignment.rescue_case_id == case_id,
                    RescueAssignment.assignment_status == AssignmentStatus.PENDING,
                )
                .count()
            )
            if remaining_pending == 0:
                cls.dispatch_case(db, case_id)

        return len(expired_offers)

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
        # Lock offer
        dialect_name = db.bind.dialect.name if db.bind else "sqlite"
        offer_query = db.query(RescueAssignment).filter(
            RescueAssignment.id == offer_id, RescueAssignment.rescuer_id == rescuer_id
        )
        if dialect_name == "postgresql":
            offer = offer_query.with_for_update().first()
        else:
            offer = offer_query.first()

        if not offer:
            raise NotFoundException("Dispatch offer not found for this rescuer")

        if offer.assignment_status != AssignmentStatus.PENDING:
            raise ConflictException(
                f"Offer is no longer pending (current status: {offer.assignment_status.value})"
            )

        now = datetime.utcnow()
        if offer.expires_at and offer.expires_at < now:
            offer.assignment_status = AssignmentStatus.EXPIRED
            offer.expired_at = now
            db.commit()
            raise ConflictException("Dispatch offer has expired")

        # Concurrency row-locking on RescueCase
        case_query = db.query(RescueCase).filter(RescueCase.id == offer.rescue_case_id)
        if dialect_name == "postgresql":
            case = case_query.with_for_update().first()
        else:
            case = case_query.first()

        if not case:
            raise NotFoundException("Rescue case not found")

        if case.status not in [RescueStatus.TRIAGED, RescueStatus.SEARCHING_RESPONDER]:
            offer.assignment_status = AssignmentStatus.CANCELLED
            db.commit()
            raise ConflictException("This rescue has already been assigned to another responder or closed.")

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

        return offer

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
