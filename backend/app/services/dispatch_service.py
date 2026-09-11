import math
from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.rescue_case import RescueCase
from app.models.user import User
from app.models.rescuer_profile import RescuerProfile
from app.core.constants import RescueStatus, RescuePriority, RescuerAvailability, UserRole

PRIORITY_ORDER = {
    RescuePriority.CRITICAL: 4,
    RescuePriority.URGENT: 3,
    RescuePriority.MODERATE: 2,
    RescuePriority.GENERAL: 1,
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
    def find_nearby_rescues(
        db: Session,
        lat: float,
        lng: float,
        radius_km: float = 10.0
    ) -> List[Tuple[RescueCase, float]]:
        """
        Geographic filtering for available rescue cases.
        Uses native PostGIS on PostgreSQL if available, otherwise Haversine math.
        Ranks by:
          1. Priority (CRITICAL > URGENT > MODERATE > GENERAL)
          2. Distance (closest first)
          3. Age (oldest first)
        """
        open_statuses = [RescueStatus.TRIAGED, RescueStatus.SEARCHING_RESPONDER]
        dialect_name = db.bind.dialect.name if db.bind else "sqlite"

        results: List[Tuple[RescueCase, float]] = []

        if dialect_name == "postgresql":
            # Native PostGIS query
            point_geom = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
            query = (
                db.query(
                    RescueCase,
                    (func.ST_Distance(RescueCase.location, point_geom) / 1000.0).label("dist_km")
                )
                .filter(
                    RescueCase.status.in_(open_statuses),
                    func.ST_DWithin(RescueCase.location, point_geom, radius_km * 1000.0)
                )
                .all()
            )
            for case, dist in query:
                results.append((case, round(float(dist), 2)))
        else:
            # SQLite / standard SQL fallback with Python Haversine calculation
            cases = db.query(RescueCase).filter(RescueCase.status.in_(open_statuses)).all()
            for case in cases:
                dist = haversine_distance(lat, lng, case.latitude, case.longitude)
                if dist <= radius_km:
                    results.append((case, dist))

        # Sort: Highest priority first, then closest distance, then oldest created_at
        results.sort(
            key=lambda item: (
                -PRIORITY_ORDER.get(item[0].triage_priority, 0),
                item[1],
                item[0].created_at
            )
        )

        return results

    @staticmethod
    def find_nearby_available_rescuers(
        db: Session,
        case_lat: float,
        case_lng: float,
        radius_km: float = 10.0
    ) -> List[Tuple[User, float]]:
        """Find available responders within the specified radius."""
        profiles = (
            db.query(RescuerProfile)
            .filter(
                RescuerProfile.availability_status == RescuerAvailability.AVAILABLE,
                RescuerProfile.latitude.isnot(None),
                RescuerProfile.longitude.isnot(None),
            )
            .all()
        )

        nearby = []
        for p in profiles:
            dist = haversine_distance(case_lat, case_lng, p.latitude, p.longitude)
            if dist <= radius_km:
                nearby.append((p.user, dist))

        nearby.sort(key=lambda x: x[1])
        return nearby
