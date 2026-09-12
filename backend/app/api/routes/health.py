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
def health_readiness(response: Response, db: Session = Depends(get_db)):
    """Readiness probe checking critical downstream dependencies: Database, Redis, and Worker."""
    checks = {
        "database": "unknown",
        "redis": "skipped",
        "worker": "skipped",
    }
    healthy = True

    # 1. Database check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "connected"
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
        except Exception as e:
            logger.warning(f"Health check warning on Redis/Worker: {e}")
            checks["redis"] = "disconnected"
            checks["worker"] = "unavailable"
            if settings.ENVIRONMENT in ["production", "staging"]:
                healthy = False

    # 3. Storage Provider check
    try:
        from app.services.storage_service import storage_service, LocalStorageProvider, S3StorageProvider
        if isinstance(storage_service, (LocalStorageProvider, S3StorageProvider)):
            checks["storage"] = "healthy"
        else:
            checks["storage"] = "healthy"
    except Exception as e:
        logger.warning(f"Storage readiness check warning: {e}")
        checks["storage"] = "unhealthy"

    # 4. Firebase Cloud Messaging configuration check
    try:
        from app.services.notification_service import _firebase_initialized
        checks["firebase"] = "configured" if _firebase_initialized else "unconfigured"
    except Exception:
        checks["firebase"] = "unconfigured"

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    services = {
        "database": "healthy" if checks["database"] == "connected" else "unhealthy",
        "redis": "healthy" if checks["redis"] == "connected" else checks["redis"],
        "celery": "healthy" if checks["worker"] == "active" else checks["worker"],
        "storage": checks["storage"],
        "firebase": checks["firebase"],
    }

    return {
        "status": "ready" if healthy else "degraded",
        "environment": settings.ENVIRONMENT,
        "services": services,
        "checks": checks,
    }
