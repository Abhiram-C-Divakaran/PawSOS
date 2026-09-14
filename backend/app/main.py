import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.config import settings
from app.core.rate_limiter import limiter
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.middleware import RequestIDMiddleware

# Sentry initialization if DSN configured (Requirement 36)
if settings.SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=1.0 if settings.ENVIRONMENT == "development" else 0.1,
    )

from app.api.routes import (
    auth,
    rescues,
    rescuers,
    dispatch,
    notifications,
    ngo,
    veterinary,
    veterinary_facilities,
    animals,
    uploads,
    health,
    foster,
    adoptions,
)

# Production & Staging security & database checks
if settings.ENVIRONMENT in ["production", "staging"]:
    insecure_keys = ["secret", "dev_secret_key_change_in_production", ""]
    if settings.JWT_SECRET_KEY in insecure_keys or len(settings.JWT_SECRET_KEY) < 32:
        raise RuntimeError(f"FATAL: Insecure or default JWT_SECRET_KEY detected in {settings.ENVIRONMENT} environment.")
    
    # Production/staging database must use PostgreSQL + PostGIS. Fail startup if SQLite.
    if "sqlite" in settings.DATABASE_URL.lower():
        raise RuntimeError(
            f"FATAL: {settings.ENVIRONMENT.capitalize()} database must use PostgreSQL with PostGIS. SQLite is strictly prohibited."
        )

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)

app = FastAPI(
    title="PawReach API",
    description="Backend API for PawReach rescue coordination platform (MVP Phase 2).",
    version="2.0.0"
)

# Rate Limiter state & handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)

# CORS configuration
if settings.CORS_ORIGINS:
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
elif settings.ENVIRONMENT == "development":
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
    ]
else:
    origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount uploads static directory for local storage serving
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API Routers
app.include_router(health.router, tags=["Health"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(rescues.router, prefix="/api/v1/rescues", tags=["Rescue Cases"])
app.include_router(rescuers.router, prefix="/api/v1/rescuers", tags=["Rescuers"])
app.include_router(dispatch.router, prefix="/api/v1/dispatch", tags=["Automatic Dispatch"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Push & In-App Notifications"])
app.include_router(ngo.router, prefix="/api/v1/ngo", tags=["NGO Operations Command Center"])
app.include_router(veterinary_facilities.router, prefix="/api/v1/veterinary", tags=["Veterinary Facilities"])
app.include_router(veterinary.router, prefix="/api/v1/rescues/{case_id}/treatments", tags=["Veterinary Treatments"])
app.include_router(uploads.router, prefix="/api/v1/uploads", tags=["Uploads"])
app.include_router(animals.router, prefix="/api/v1/animals", tags=["Animals"])
app.include_router(foster.router, prefix="/api/v1/foster", tags=["Foster Care Operations"])
app.include_router(foster.ngo_router, prefix="/api/v1/ngo/foster", tags=["NGO Foster Operations"])
app.include_router(adoptions.router, prefix="/api/v1/adoptions", tags=["Public Adoptions Catalog"])
app.include_router(adoptions.applicant_router, prefix="/api/v1/adoption-applications", tags=["My Adoption Applications"])
app.include_router(adoptions.ngo_router, prefix="/api/v1/ngo/adoptions", tags=["NGO Adoption Operations"])

@app.get("/")
def root():
    return {
        "message": "Welcome to PawReach API (Phase 2)",
        "version": "2.0.0",
        "environment": settings.ENVIRONMENT
    }
