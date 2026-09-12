from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
def health_liveness():
    """Basic liveness probe verifying the API process is alive and responsive."""
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0"
    }

@router.get("/health/ready")
@router.get("/health/readiness")
def health_readiness(response: Response, db: Session = Depends(get_db)):
    """Readiness probe checking critical downstream dependencies: Database, PostGIS, Redis, Worker, Storage, Firebase."""
    checks = {
        "database": "unknown",
        "postgis": "unknown",
        "redis": "skipped",
        "worker": "skipped",
        "storage": "unknown",
        "firebase": "unconfigured",
    }
    healthy = True

    # 1. Database check & PostGIS verification
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "connected"

        dialect_name = db.bind.dialect.name if db.bind else "sqlite"
        if dialect_name == "postgresql":
            try:
                db.execute(text("SELECT PostGIS_Version();"))
                checks["postgis"] = "available"
            except Exception as e:
                logger.error(f"PostGIS check failed on PostgreSQL: {e}")
                checks["postgis"] = "unavailable"
                if settings.ENVIRONMENT in ["production", "staging"]:
                    healthy = False
        else:
            checks["postgis"] = "simulated"
    except Exception as e:
        logger.error(f"Health check failed on database: {e}")
        checks["database"] = "disconnected"
        healthy = False

    # 2. Redis and Worker Heartbeat check
    if settings.REDIS_URL:
        try:
            import redis
            r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
            r.ping()
            checks["redis"] = "connected"

            heartbeat = r.get("celery_worker_heartbeat")
            if heartbeat:
                checks["worker"] = "active"
            else:
                checks["worker"] = "no_heartbeat"
                if settings.ENVIRONMENT in ["production", "staging"]:
                    checks["worker"] = "degraded"
                    healthy = False
        except Exception as e:
            logger.warning(f"Health check warning on Redis/Worker: {e}")
            checks["redis"] = "disconnected"
            checks["worker"] = "unavailable"
            if settings.ENVIRONMENT in ["production", "staging"]:
                healthy = False

    # 3. Storage Provider check
    try:
        from app.services.storage_service import storage_service
        is_storage_ok = storage_service.check_health()
        checks["storage"] = "healthy" if is_storage_ok else "unhealthy"
        if not is_storage_ok and settings.ENVIRONMENT in ["production", "staging"]:
            healthy = False
    except Exception as e:
        logger.warning(f"Storage readiness check warning: {e}")
        checks["storage"] = "unhealthy"
        if settings.ENVIRONMENT in ["production", "staging"]:
            healthy = False

    # 4. Firebase Cloud Messaging configuration check
    # Policy: Missing Firebase is considered 'degraded' rather than fatal to allow offline/local rescue dispatch
    try:
        from app.services.notification_service import _firebase_initialized
        checks["firebase"] = "configured" if _firebase_initialized else "unconfigured"
    except Exception:
        checks["firebase"] = "unconfigured"

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    overall_status = "ready" if healthy else "degraded"
    if checks["database"] == "disconnected":
        overall_status = "offline"

    services = {
        "database": "healthy" if checks["database"] == "connected" else "unhealthy",
        "postgis": checks["postgis"],
        "redis": "healthy" if checks["redis"] == "connected" else checks["redis"],
        "celery": "healthy" if checks["worker"] == "active" else checks["worker"],
        "storage": checks["storage"],
        "firebase": checks["firebase"],
    }

    return {
        "status": overall_status,
        "environment": settings.ENVIRONMENT,
        "services": services,
        "checks": checks,
    }
