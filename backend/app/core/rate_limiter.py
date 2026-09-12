from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

def create_limiter() -> Limiter:
    storage_uri = "memory://"
    if settings.REDIS_URL and settings.ENVIRONMENT == "production":
        storage_uri = settings.REDIS_URL

    return Limiter(
        key_func=get_remote_address,
        default_limits=["120/minute"],
        storage_uri=storage_uri,
    )

limiter = create_limiter()
