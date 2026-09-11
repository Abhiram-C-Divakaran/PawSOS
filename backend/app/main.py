import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.api.routes import (
    auth,
    rescues,
    rescuers,
    veterinary,
    veterinary_facilities,
    animals,
    uploads,
)

# Production security checks
if settings.ENVIRONMENT == "production":
    insecure_keys = ["secret", "dev_secret_key_change_in_production", ""]
    if settings.JWT_SECRET_KEY in insecure_keys or len(settings.JWT_SECRET_KEY) < 32:
        raise RuntimeError("FATAL: Insecure or default JWT_SECRET_KEY detected in production environment.")

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)

app = FastAPI(
    title="PawReach API",
    description="Backend API for PawReach rescue coordination platform.",
    version="1.0.0"
)

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

# Mount uploads static directory for real image serving
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(rescues.router, prefix="/api/v1/rescues", tags=["Rescue Cases"])
app.include_router(rescuers.router, prefix="/api/v1/rescuers", tags=["Rescuers"])
app.include_router(veterinary_facilities.router, prefix="/api/v1/veterinary", tags=["Veterinary Facilities"])
app.include_router(veterinary.router, prefix="/api/v1/rescues/{case_id}/treatments", tags=["Veterinary Treatments"])
app.include_router(uploads.router, prefix="/api/v1/uploads", tags=["Uploads"])
app.include_router(animals.router, prefix="/api/v1/animals", tags=["Animals"])

@app.get("/")
def root():
    return {
        "message": "Welcome to PawReach API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }
