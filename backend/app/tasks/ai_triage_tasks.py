import json
import logging
import uuid
import concurrent.futures
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app.tasks.celery_app import celery_app
from app.database import SessionLocal
from app.models.rescue_case import RescueCase
from app.models.animal_image import AnimalImage
from app.models.triage_assessment import TriageAssessment
from app.models.rescue_status_history import RescueStatusHistory
from app.models.user import User
from app.core.constants import RescuePriority, RescueStatus, UserRole
from app.services.storage_service import storage_service
from app.services.notification_service import NotificationService
from app.ai.factory import get_vision_triage_provider
from app.ai.fusion import HybridTriageFusionEngine
from app.ai.base import AITriageDisabledException, AITriageTimeoutException
from app.config import settings

logger = logging.getLogger(__name__)

def run_provider_with_timeout(provider, image_bytes: bytes, context: dict, timeout_seconds: float):
    """
    Execute provider.assess with real timeout enforcement using ThreadPoolExecutor.
    Guarantees cross-platform timeout enforcement without crashing Celery --pool=solo workers.
    """
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(provider.assess, image_bytes, context)
    try:
        return future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError:
        executor.shutdown(wait=False, cancel_futures=True)
        raise AITriageTimeoutException(
            f"Provider assessment timed out after {timeout_seconds} seconds."
        )
    except Exception:
        executor.shutdown(wait=False)
        raise
    else:
        executor.shutdown(wait=False)


@celery_app.task(
    name="app.tasks.ai_triage_tasks.perform_ai_triage_task",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    queue="ai_triage",
    soft_time_limit=30,
    time_limit=45,
)
def perform_ai_triage_task(self, case_id_str: str, image_id_str: str, db_session=None):
    """
    Asynchronous Celery task for AI-assisted visual triage.
    Executes in background without blocking synchronous report submission or dispatch.
    Applies strict non-downgrade fusion policy.
    """
    logger.info(f"[AI_TRIAGE_TASK] Starting visual triage assessment for case={case_id_str}, image={image_id_str}")
    db = db_session if db_session is not None else SessionLocal()

    try:
        case_id = uuid.UUID(case_id_str)
        image_id = uuid.UUID(image_id_str) if image_id_str else None

        case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
        if not case:
            logger.warning(f"[AI_TRIAGE_TASK] Rescue case {case_id_str} not found. Aborting.")
            return {"status": "ABORTED", "reason": "CASE_NOT_FOUND"}

        image = db.query(AnimalImage).filter(AnimalImage.id == image_id).first() if image_id else None
        if image and image.rescue_case_id != case.id:
            logger.warning(
                f"[AI_TRIAGE_TASK] Image {image_id_str} does not belong to case {case_id_str}. Aborting."
            )
            return {"status": "ABORTED", "reason": "IMAGE_CASE_MISMATCH"}

        # Check feature flag
        if not settings.AI_TRIAGE_ENABLED:
            logger.info(f"[AI_TRIAGE_TASK] AI Triage is disabled in settings. Recording skipped assessment.")
            existing_assessment = (
                db.query(TriageAssessment)
                .filter(
                    TriageAssessment.rescue_case_id == case.id,
                    TriageAssessment.model_name == settings.AI_TRIAGE_MODEL_NAME,
                    TriageAssessment.model_version == settings.AI_TRIAGE_MODEL_VERSION,
                )
                .first()
            )
            if existing_assessment:
                existing_assessment.status = "SKIPPED"
                existing_assessment.explanation = "AI visual triage is disabled in configuration. Synchronous rule priority active."
                existing_assessment.completed_at = datetime.utcnow()
                db.commit()
                return {"status": "SKIPPED", "reason": "Feature disabled"}

            try:
                with db.begin_nested():
                    assessment = TriageAssessment(
                        rescue_case_id=case.id,
                        animal_image_id=image.id if image else None,
                        source="RULES",
                        status="SKIPPED",
                        suggested_priority=case.triage_priority,
                        score=case.triage_score,
                        explanation="AI visual triage is disabled in configuration. Synchronous rule priority active.",
                        provider="disabled",
                        model_name=settings.AI_TRIAGE_MODEL_NAME,
                        model_version=settings.AI_TRIAGE_MODEL_VERSION,
                        completed_at=datetime.utcnow(),
                    )
                    db.add(assessment)
                    db.flush()
                db.commit()
            except IntegrityError:
                logger.info(f"[AI_TRIAGE_TASK] Concurrent skipped assessment insert detected for case={case.case_number}.")
            return {"status": "SKIPPED", "reason": "Feature disabled"}

        provider = get_vision_triage_provider()

        # Check idempotency: check if an assessment for this case/model_version is already COMPLETED
        existing_assessment = (
            db.query(TriageAssessment)
            .filter(
                TriageAssessment.rescue_case_id == case.id,
                TriageAssessment.model_name == provider.model_name,
                TriageAssessment.model_version == provider.model_version,
            )
            .first()
        )

        if existing_assessment and existing_assessment.status == "COMPLETED":
            logger.info(f"[AI_TRIAGE_TASK] Assessment already completed for case={case.case_number}. Skipping.")
            return {"status": "ALREADY_COMPLETED", "assessment_id": str(existing_assessment.id)}

        if not existing_assessment:
            try:
                with db.begin_nested():
                    assessment = TriageAssessment(
                        rescue_case_id=case.id,
                        animal_image_id=image.id if image else None,
                        source="IMAGE_AI",
                        status="PENDING",
                        provider=provider.provider_name,
                        model_name=provider.model_name,
                        model_version=provider.model_version,
                    )
                    db.add(assessment)
                    db.flush()
                db.commit()
                db.refresh(assessment)
            except IntegrityError:
                logger.info(f"[AI_TRIAGE_TASK] Concurrent insert detected for case={case.case_number}. Reusing existing.")
                existing_assessment = (
                    db.query(TriageAssessment)
                    .filter(
                        TriageAssessment.rescue_case_id == case.id,
                        TriageAssessment.model_name == provider.model_name,
                        TriageAssessment.model_version == provider.model_version,
                    )
                    .first()
                )
                if existing_assessment and existing_assessment.status == "COMPLETED":
                    return {"status": "ALREADY_COMPLETED", "assessment_id": str(existing_assessment.id)}
                assessment = existing_assessment
        else:
            assessment = existing_assessment
            assessment.status = "PENDING"
            db.commit()

        if not image or not image.image_url:
            logger.info(f"[AI_TRIAGE_TASK] No evidence image provided for case={case.case_number}. Skipping.")
            assessment.status = "SKIPPED"
            assessment.explanation = "No evidence image attached to rescue report."
            assessment.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "SKIPPED", "reason": "No image"}

        # Fetch image bytes safely via internal storage method
        try:
            image_bytes = storage_service.get_image_bytes(image.image_url)
        except Exception as img_err:
            logger.error(f"[AI_TRIAGE_TASK] Could not load image bytes for case={case.case_number}: {type(img_err).__name__}")
            assessment.status = "FAILED"
            assessment.sanitized_error_code = "IMAGE_LOAD_ERROR"
            assessment.explanation = "Evidence image could not be loaded from storage."
            assessment.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "FAILED", "error": "IMAGE_LOAD_ERROR"}

        # Invoke provider with non-PII context only
        context = {
            "species": case.species,
            "case_id": str(case.id),
        }

        try:
            ai_result = run_provider_with_timeout(
                provider, image_bytes, context, timeout_seconds=settings.AI_TRIAGE_TIMEOUT_SECONDS
            )
        except AITriageDisabledException:
            assessment.status = "SKIPPED"
            assessment.explanation = "AI visual triage provider is unconfigured or disabled."
            assessment.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "SKIPPED", "reason": "PROVIDER_DISABLED"}
        except AITriageTimeoutException:
            logger.warning(
                f"[AI_TRIAGE_TASK] Provider assessment timed out after {settings.AI_TRIAGE_TIMEOUT_SECONDS}s for case={case.case_number}"
            )
            assessment.status = "FAILED"
            assessment.sanitized_error_code = "PROVIDER_TIMEOUT"
            assessment.explanation = "Visual assessment service timed out."
            assessment.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "FAILED", "error": "PROVIDER_TIMEOUT"}
        except Exception as assess_err:
            logger.warning(
                f"[AI_TRIAGE_TASK] Provider assessment failed for case={case.case_number}: {type(assess_err).__name__}"
            )
            assessment.status = "FAILED"
            assessment.sanitized_error_code = "PROVIDER_ERROR"
            assessment.explanation = "Visual assessment service temporarily unavailable."
            assessment.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "FAILED", "error": "PROVIDER_ERROR"}

        # Apply non-downgrade Hybrid Fusion Policy
        existing_reasons = [r.strip() for r in (case.triage_reason or "").split(",") if r.strip()]
        fusion_result = HybridTriageFusionEngine.fuse(
            rule_priority=case.triage_priority,
            rule_score=case.triage_score or 20,
            rule_reasons=existing_reasons,
            ai_result=ai_result,
            min_confidence=settings.AI_TRIAGE_MIN_CONFIDENCE,
        )

        # Update assessment record
        assessment.status = "COMPLETED"
        assessment.source = fusion_result.source
        assessment.suggested_priority = ai_result.suggested_priority
        assessment.score = ai_result.score
        assessment.confidence = ai_result.confidence
        assessment.visible_signs = json.dumps(ai_result.visible_signs)
        assessment.explanation = ai_result.explanation
        assessment.completed_at = datetime.utcnow()

        # If priority escalated: update case and trigger dispatch adjustment
        if fusion_result.escalated:
            logger.info(
                f"[AI_TRIAGE_TASK] Priority ESCALATED for case={case.case_number}: "
                f"{case.triage_priority.value} -> {fusion_result.final_priority.value}"
            )
            old_priority = case.triage_priority
            case.triage_priority = fusion_result.final_priority
            case.triage_score = fusion_result.final_score
            case.triage_reason = ", ".join(fusion_result.final_reasons)

            # Log status history for audit trail
            history = RescueStatusHistory(
                rescue_case_id=case.id,
                previous_status=case.status,
                new_status=case.status,
                notes=f"AI visual triage escalated priority from {old_priority.value} to {case.triage_priority.value}",
            )
            db.add(history)

            # If escalated to CRITICAL, alert scoped NGO Admins and Super Admins immediately
            if case.triage_priority == RescuePriority.CRITICAL:
                recipients = NotificationService.get_critical_alert_recipients(
                    db=db,
                    organization_id=case.organization_id,
                )
                for admin in recipients:
                    NotificationService.notify_user(
                        db=db,
                        user_id=admin.id,
                        title=f"🚨 AI ESCALATION to CRITICAL: Case {case.case_number}",
                        message=f"Case #{case.case_number} ({case.species}) escalated to CRITICAL by visual review: {ai_result.explanation}",
                        notification_type="CRITICAL_ALERT",
                        rescue_case_id=case.id,
                        data={"case_id": str(case.id), "priority": "CRITICAL"},
                    )

            # If actively searching responders, notify dispatch service of escalation
            if case.status == RescueStatus.SEARCHING_RESPONDER:
                from app.services.dispatch_service import DispatchService
                DispatchService.handle_priority_escalation(db, case, fusion_result.final_priority)

        db.commit()
        logger.info(f"[AI_TRIAGE_TASK] Visual triage completed successfully for case {case.case_number}")
        return {
            "status": "COMPLETED",
            "escalated": fusion_result.escalated,
            "final_priority": fusion_result.final_priority.value,
        }

    except Exception as e:
        db.rollback()
        logger.error(
            f"[AI_TRIAGE_TASK] Unexpected failure during visual triage for case={case_id_str}",
            exc_info=True,
        )
        # Attempt retry if Celery retry count remains
        try:
            self.retry(exc=e)
        except Exception:
            try:
                cleanup_db = SessionLocal()
                failed_assessment = (
                    cleanup_db.query(TriageAssessment)
                    .filter(
                        TriageAssessment.rescue_case_id == uuid.UUID(case_id_str),
                        TriageAssessment.status == "PENDING",
                    )
                    .first()
                )
                if failed_assessment:
                    failed_assessment.status = "FAILED"
                    failed_assessment.sanitized_error_code = "UNEXPECTED_ERROR"
                    failed_assessment.explanation = "Visual assessment encountered an unexpected error."
                    failed_assessment.completed_at = datetime.utcnow()
                    cleanup_db.commit()
                cleanup_db.close()
            except Exception:
                pass
        return {"status": "ERROR", "error": "UNEXPECTED_ERROR"}
    finally:
        if db_session is None:
            db.close()
