from typing import List, Optional
from app.ai.schemas import AITriageResult, HybridFusionResult
from app.core.constants import RescuePriority
from app.config import settings

PRIORITY_RANK = {
    RescuePriority.GENERAL: 1,
    RescuePriority.MODERATE: 2,
    RescuePriority.URGENT: 3,
    RescuePriority.CRITICAL: 4,
}

class HybridTriageFusionEngine:
    """
    Combines synchronous rule-based emergency triage with asynchronous AI visual analysis.
    Enforces strict safety invariants:
    - AI CANNOT downgrade a rule-based priority.
    - AI CANNOT override hard-safety CRITICAL results.
    - Low-confidence AI (< min_confidence) causes no priority alteration.
    - Missing, failed, or timed-out AI preserves rule priority and execution.
    - All reasons preserve distinct provenance (Reported symptoms vs AI visual advisory).
    """

    @classmethod
    def fuse(
        cls,
        rule_priority: RescuePriority,
        rule_score: int,
        rule_reasons: List[str],
        ai_result: Optional[AITriageResult],
        min_confidence: Optional[float] = None,
    ) -> HybridFusionResult:
        threshold = min_confidence if min_confidence is not None else settings.AI_TRIAGE_MIN_CONFIDENCE

        # Case 1: No AI assessment available or AI failed
        if ai_result is None:
            return HybridFusionResult(
                final_priority=rule_priority,
                final_score=rule_score,
                final_reasons=list(rule_reasons),
                source="RULES",
                escalated=False,
                ai_status="SKIPPED",
            )

        ai_rank = PRIORITY_RANK.get(ai_result.suggested_priority, 1)
        rule_rank = PRIORITY_RANK.get(rule_priority, 1)

        # Case 2: Rule priority is already CRITICAL -> Cannot be escalated, will never be downgraded
        if rule_priority == RescuePriority.CRITICAL:
            reasons = list(rule_reasons)
            if ai_result.confidence >= threshold and ai_result.explanation:
                reasons.append(
                    f"AI Visual Corroboration: {ai_result.explanation} (Confidence: {int(ai_result.confidence * 100)}%)"
                )
            return HybridFusionResult(
                final_priority=RescuePriority.CRITICAL,
                final_score=max(rule_score, ai_result.score or 0),
                final_reasons=reasons,
                source="RULES",
                escalated=False,
                ai_status="COMPLETED",
            )

        # Case 3: AI confidence is below threshold -> Informative advisory only, no priority change
        if ai_result.confidence < threshold:
            reasons = list(rule_reasons)
            if ai_result.explanation:
                reasons.append(
                    f"AI Visual Advisory (Low Confidence {int(ai_result.confidence * 100)}% < {int(threshold * 100)}%): {ai_result.explanation}"
                )
            return HybridFusionResult(
                final_priority=rule_priority,
                final_score=rule_score,
                final_reasons=reasons,
                source="RULES",
                escalated=False,
                ai_status="COMPLETED",
            )

        # Case 4: AI suggests higher priority with sufficient confidence -> ESCALATE
        if ai_rank > rule_rank:
            escalation_reasons = list(rule_reasons)
            escalation_reasons.append(
                f"AI Visual Escalation ({rule_priority.value} -> {ai_result.suggested_priority.value}): "
                f"{ai_result.explanation} (Confidence: {int(ai_result.confidence * 100)}%)"
            )
            return HybridFusionResult(
                final_priority=ai_result.suggested_priority,
                final_score=max(rule_score, ai_result.score or 0),
                final_reasons=escalation_reasons,
                source="HYBRID",
                escalated=True,
                ai_status="COMPLETED",
            )

        # Case 5: AI suggests equal or lower priority -> Keep rule priority (NO DOWNGRADE)
        reasons = list(rule_reasons)
        if ai_result.explanation:
            reasons.append(
                f"AI Visual Advisory (Maintained {rule_priority.value}): {ai_result.explanation} (Confidence: {int(ai_result.confidence * 100)}%)"
            )
        return HybridFusionResult(
            final_priority=rule_priority,
            final_score=max(rule_score, ai_result.score or 0),
            final_reasons=reasons,
            source="RULES",
            escalated=False,
            ai_status="COMPLETED",
        )
