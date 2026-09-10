from sqlalchemy.orm import Session
from app.models.user import User
from app.models.rescue_assignment import RescueAssignment
from app.core.constants import UserRole, RescuerAvailability
from typing import List

class DispatchService:
    @staticmethod
    def find_nearest_responders(db: Session, lat: float, lng: float, radius_km: float = 5.0) -> List[User]:
        """
        Mock implementation of PostGIS nearest responders query for MVP.
        In a real scenario, this uses GeoAlchemy2 to query `ST_DWithin` and `ST_Distance`.
        For now, we fetch available rescuers and mock a distance calculation.
        """
        # Fetch available rescuers
        # NOTE: MVP assumes we don't have PostGIS coords for rescuers yet, just returning all available for the demo.
        rescuers = db.query(User).filter(
            User.role == UserRole.RESCUER,
            User.is_active == True,
            # User.availability_status == RescuerAvailability.AVAILABLE # Assuming added to rescuer profile
        ).all()
        
        # Sort by mocked distance
        return rescuers

    @staticmethod
    def calculate_dispatch_score(distance_km: float, availability: bool, experience: int = 1) -> float:
        """
        Calculate dispatch score based on weighting.
        """
        score = 0.0
        if distance_km < 2:
            score += 40
        elif distance_km < 5:
            score += 20
            
        if availability:
            score += 25
            
        score += (experience * 5)
        return min(score, 100)
