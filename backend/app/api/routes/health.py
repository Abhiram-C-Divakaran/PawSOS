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
    """Readiness probe checking critical downstream dependencies: Database and Redis."""
    checks = {
        "database": "unknown",
        "redis": "skipped",
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

    # 2. Redis check if configured
    if settings.REDIS_URL and settings.ENVIRONMENT == "production":
        try:
            import redis
            r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
            r.ping()
            checks["redis"] = "connected"
        except Exception as e:
            logger.error(f"Health check failed on Redis: {e}")
            checks["redis"] = "disconnected"
            healthy = False

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if healthy else "degraded",
        "environment": settings.ENVIRONMENT,
        "checks": checks
    }
