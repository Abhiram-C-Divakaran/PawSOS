from app.core.constants import RescuePriority
from typing import Dict, Any

class TriageService:
    @staticmethod
    def calculate_triage(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        MVP Rule-Based Triage Engine.
        Does not replace veterinary diagnosis.
        """
        bleeding = inputs.get("bleeding", False)
        can_walk = inputs.get("can_walk", True)
        conscious = inputs.get("conscious", True)
        vehicle_accident = inputs.get("vehicle_accident", False)
        breathing_difficulty = inputs.get("breathing_difficulty", False)
        
        score = 20 # Base score for any report
        reasons = []
        priority = RescuePriority.GENERAL

        if not conscious:
            score += 80
            reasons.append("Animal is unconscious")
            priority = RescuePriority.CRITICAL

        if breathing_difficulty:
            score += 60
            reasons.append("Reported breathing difficulty")
            if priority != RescuePriority.CRITICAL:
                priority = RescuePriority.CRITICAL

        if bleeding:
            score += 40
            reasons.append("Visible bleeding reported")
            if not can_walk:
                score += 20
                if priority != RescuePriority.CRITICAL:
                    priority = RescuePriority.CRITICAL
            elif priority == RescuePriority.GENERAL:
                priority = RescuePriority.URGENT

        if vehicle_accident:
            score += 50
            reasons.append("Vehicle collision reported")
            if not can_walk and priority != RescuePriority.CRITICAL:
                priority = RescuePriority.CRITICAL
            elif priority in (RescuePriority.GENERAL, RescuePriority.MODERATE):
                priority = RescuePriority.URGENT

        if not can_walk and not vehicle_accident and not bleeding:
            score += 30
            reasons.append("Animal unable to walk")
            if priority == RescuePriority.GENERAL:
                priority = RescuePriority.MODERATE

        score = min(score, 100)

        return {
            "score": score,
            "priority": priority,
            "reasons": reasons
        }
