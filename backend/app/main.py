from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import auth, rescues, veterinary, animals # We will create these shortly

app = FastAPI(
    title="PawReach API",
    description="Backend API for PawReach rescue coordination platform.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(rescues.router, prefix="/api/v1/rescues", tags=["Rescue Cases"])
app.include_router(veterinary.router, prefix="/api/v1/rescues/{case_id}/treatments", tags=["Veterinary"])
app.include_router(animals.router, prefix="/api/v1/animals", tags=["Animals"])

@app.get("/")
def root():
    return {"message": "Welcome to PawReach API"}
