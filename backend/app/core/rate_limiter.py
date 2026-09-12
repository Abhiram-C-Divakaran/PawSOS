import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

def create_limiter() -> Limiter:
    storage_uri = "memory://"
    if settings.REDIS_URL and settings.ENVIRONMENT == "production":
        storage_uri = settings.REDIS_URL

    is_testing = (
        settings.DISABLE_RATE_LIMITING
        or os.getenv("CI") == "true"
        or os.getenv("TESTING") == "true"
        or os.getenv("DISABLE_RATE_LIMITING") == "true"
        or settings.ENVIRONMENT == "test"
    )

    return Limiter(
        key_func=get_remote_address,
        default_limits=["120/minute"],
        storage_uri=storage_uri,
        enabled=not is_testing,
    )

limiter = create_limiter()
