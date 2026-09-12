import logging
from datetime import datetime
from app.tasks.celery_app import celery_app
from app.database import SessionLocal
from app.config import settings

logger = logging.getLogger(__name__)

@celery_app.task(name="app.tasks.dispatch_tasks.worker_heartbeat_task")
def worker_heartbeat_task() -> dict:
    """Periodic task updating Redis worker heartbeat key."""
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
        now_iso = datetime.utcnow().isoformat()
        r.set("celery_worker_heartbeat", now_iso, ex=settings.CELERY_HEARTBEAT_TTL_SECONDS)
        return {"status": "ok", "heartbeat_at": now_iso}
    except Exception as e:
        logger.warning(f"Could not record worker heartbeat in Redis: {e}")
        return {"status": "error", "detail": str(e)}

@celery_app.task(name="app.tasks.dispatch_tasks.expire_dispatch_offers_task")
def expire_dispatch_offers_task(db_session=None) -> dict:
    """
    Periodic task running every 15-30s to expire stale dispatch offers
    and escalate unaccepted cases through radius expansion or UNRESOLVED state.
    """
    from app.services.dispatch_service import DispatchService
    own_session = False
    if db_session is not None:
        db = db_session
    else:
        db = SessionLocal()
        own_session = True
    try:
        expired_count, escalated_count, failed_count = DispatchService.process_dispatch_lifecycle(db)
        return {
            "status": "success",
            "expired_offers": expired_count,
            "escalated_cases": escalated_count,
            "exhausted_unresolved_cases": failed_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error executing expire_dispatch_offers_task: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    finally:
        if own_session:
            db.close()

@celery_app.task(name="app.tasks.dispatch_tasks.dispatch_case_task")
def dispatch_case_task(case_id: str, db_session=None) -> dict:
    """Asynchronous background dispatch trigger for a rescue case."""
    import uuid
    from app.services.dispatch_service import DispatchService
    own_session = False
    if db_session is not None:
        db = db_session
    else:
        db = SessionLocal()
        own_session = True
    try:
        offers = DispatchService.dispatch_case(db, uuid.UUID(case_id))
        return {
            "status": "success",
            "case_id": case_id,
            "offers_created": len(offers),
        }
    except Exception as e:
        logger.error(f"Error in dispatch_case_task for case {case_id}: {e}", exc_info=True)
        return {"status": "error", "case_id": case_id, "error": str(e)}
    finally:
        if own_session:
            db.close()
