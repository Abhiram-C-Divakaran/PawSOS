import pytest
from app.core.constants import RescuePriority
from app.ai.schemas import AITriageResult, HybridFusionResult
from app.ai.fusion import HybridTriageFusionEngine

def test_non_downgrade_critical_rule_invariant():
    """Rule-based CRITICAL can never be downgraded even if AI suggests GENERAL or URGENT."""
    ai_result = AITriageResult(
        suggested_priority=RescuePriority.GENERAL,
        score=20,
        confidence=0.99,
        visible_signs=["Animal is resting"],
        explanation="Animal appears calm",
    )

    fusion = HybridTriageFusionEngine.fuse(
        rule_priority=RescuePriority.CRITICAL,
        rule_score=85,
        rule_reasons=["Animal is unconscious", "Severe trauma"],
        ai_result=ai_result,
        min_confidence=0.70,
    )

    assert fusion.final_priority == RescuePriority.CRITICAL
    assert fusion.final_score == 85
    assert fusion.escalated is False
    assert fusion.source == "RULES"
    assert "Animal is unconscious" in fusion.final_reasons

def test_non_downgrade_urgent_rule_invariant():
    """Rule-based URGENT cannot be demoted by a lower AI suggestion."""
    ai_result = AITriageResult(
        suggested_priority=RescuePriority.MODERATE,
        score=30,
        confidence=0.88,
        visible_signs=["Mild limping"],
        explanation="Minor mobility issue",
    )

    fusion = HybridTriageFusionEngine.fuse(
        rule_priority=RescuePriority.URGENT,
        rule_score=60,
        rule_reasons=["Visible bleeding reported"],
        ai_result=ai_result,
        min_confidence=0.70,
    )

    assert fusion.final_priority == RescuePriority.URGENT
    assert fusion.final_score == 60
    assert fusion.escalated is False
    assert fusion.source == "RULES"

def test_escalation_from_general_to_urgent():
    """AI visual assessment can escalate GENERAL to URGENT if confidence meets threshold."""
    ai_result = AITriageResult(
        suggested_priority=RescuePriority.URGENT,
        score=70,
        confidence=0.82,
        visible_signs=["Visible laceration", "Active bleeding"],
        explanation="Active bleeding detected in limb",
    )

    fusion = HybridTriageFusionEngine.fuse(
        rule_priority=RescuePriority.GENERAL,
        rule_score=20,
        rule_reasons=[],
        ai_result=ai_result,
        min_confidence=0.70,
    )

    assert fusion.final_priority == RescuePriority.URGENT
    assert fusion.final_score == 70
    assert fusion.escalated is True
    assert fusion.source == "HYBRID"
    assert any("Active bleeding detected in limb" in r for r in fusion.final_reasons)

def test_escalation_from_urgent_to_critical():
    """AI visual assessment escalates URGENT to CRITICAL on acute trauma detection."""
    ai_result = AITriageResult(
        suggested_priority=RescuePriority.CRITICAL,
        score=95,
        confidence=0.91,
        visible_signs=["Arterial bleeding", "Extensive trauma"],
        explanation="Severe acute trauma detected visually",
    )

    fusion = HybridTriageFusionEngine.fuse(
        rule_priority=RescuePriority.URGENT,
        rule_score=60,
        rule_reasons=["Visible bleeding reported"],
        ai_result=ai_result,
        min_confidence=0.70,
    )

    assert fusion.final_priority == RescuePriority.CRITICAL
    assert fusion.final_score == 95
    assert fusion.escalated is True
    assert fusion.source == "HYBRID"
    assert any("Severe acute trauma detected visually" in r for r in fusion.final_reasons)

def test_confidence_threshold_gating():
    """AI suggestion with confidence below threshold is ignored even if higher urgency."""
    ai_result = AITriageResult(
        suggested_priority=RescuePriority.CRITICAL,
        score=90,
        confidence=0.55, # Below min_confidence=0.70
        visible_signs=["Possible blood"],
        explanation="Low confidence anomaly",
    )

    fusion = HybridTriageFusionEngine.fuse(
        rule_priority=RescuePriority.GENERAL,
        rule_score=20,
        rule_reasons=["Standard intake"],
        ai_result=ai_result,
        min_confidence=0.70,
    )

    # Escalation rejected due to low confidence
    assert fusion.final_priority == RescuePriority.GENERAL
    assert fusion.final_score == 20
    assert fusion.escalated is False
    assert fusion.source == "RULES"

def test_fusion_with_none_ai_result():
    """Fusion gracefully handles None AI result without errors."""
    fusion = HybridTriageFusionEngine.fuse(
        rule_priority=RescuePriority.MODERATE,
        rule_score=40,
        rule_reasons=["Unable to walk"],
        ai_result=None,
    )

    assert fusion.final_priority == RescuePriority.MODERATE
    assert fusion.final_score == 40
    assert fusion.escalated is False
    assert fusion.source == "RULES"
