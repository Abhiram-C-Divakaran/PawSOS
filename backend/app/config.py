import os
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_TITLE: str = "PawReach API"
    APP_DESCRIPTION: str = "Backend API for PawReach rescue coordination platform."
    APP_VERSION: str = "2.0.0"

    DATABASE_URL: str = "sqlite:///./pawsos.db"
    JWT_SECRET_KEY: str = "secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = ""
    ENVIRONMENT: str = "development"
    PROCESS_TYPE: str = Field(default_factory=lambda: os.getenv("PROCESS_TYPE", "api"))
    GIT_SHA: str = Field(
        default_factory=lambda: (
            os.getenv("GIT_SHA")
            or os.getenv("RENDER_GIT_COMMIT")
            or os.getenv("VERCEL_GIT_COMMIT_SHA")
            or os.getenv("GITHUB_SHA")
            or "unknown"
        )
    )

    # Redis & Background Tasks
    REDIS_URL: str = "redis://localhost:6379/0"

    # Cloud Storage (local, s3, cloudinary)
    STORAGE_PROVIDER: str = "local"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""
    S3_ENDPOINT_URL: str = ""
    S3_FORCE_PATH_STYLE: bool = False
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # Firebase Cloud Messaging
    FIREBASE_CREDENTIALS_PATH: str = ""
    FIREBASE_CREDENTIALS_JSON: str = ""
    REQUIRE_FIREBASE: bool = False
    FIREBASE_PROJECT_ID: str = ""

    # Cloud Storage Presigned URL Expiry
    S3_PRESIGNED_URL_EXPIRE_SECONDS: int = 900

    # Automatic Dispatch Settings
    RESPONDER_LOCATION_STALE_MINUTES: int = 30
    DISPATCH_RADIUS_LEVELS: str = "5,10,20,40"
    DISPATCH_OFFER_EXPIRY_SECONDS: int = 90
    DISPATCH_WEIGHT_DISTANCE: float = 0.40
    DISPATCH_WEIGHT_AVAILABILITY: float = 0.25
    DISPATCH_WEIGHT_EXPERIENCE: float = 0.15
    DISPATCH_WEIGHT_VEHICLE: float = 0.10
    DISPATCH_WEIGHT_RELIABILITY: float = 0.10
    DISPATCH_MAX_OFFERS_CRITICAL: int = 5
    DISPATCH_MAX_OFFERS_URGENT: int = 3
    DISPATCH_MAX_OFFERS_MODERATE: int = 2
    DISPATCH_MAX_OFFERS_GENERAL: int = 1
    DISPATCH_BEAT_INTERVAL_SECONDS: float = 2.0
    CELERY_HEARTBEAT_INTERVAL_SECONDS: float = 5.0
    CELERY_HEARTBEAT_TTL_SECONDS: int = 60
    CELERY_HEARTBEAT_THRESHOLD_SECONDS: int = 60

    # Security & Cookie Settings
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    RATE_LIMIT_PER_MINUTE: int = 60
    DISABLE_RATE_LIMITING: bool = False
    SENTRY_DSN: str = ""

    # Phase 3B: AI-Assisted Visual Triage & Safety
    AI_TRIAGE_ENABLED: bool = False
    AI_TRIAGE_PROVIDER: str = "disabled"
    AI_TRIAGE_TIMEOUT_SECONDS: float = 15.0
    AI_TRIAGE_MIN_CONFIDENCE: float = 0.70
    AI_TRIAGE_MODEL_NAME: str = "pawreach-vision-safety"
    AI_TRIAGE_MODEL_VERSION: str = "v1.0"

    @model_validator(mode="after")
    def validate_production_settings(self):
        env = (self.ENVIRONMENT or "development").lower()
        proc = (self.PROCESS_TYPE or "api").lower()
        if env in ["production", "staging"]:
            # 1. Database: PostgreSQL only, SQLite forbidden
            if "sqlite" in self.DATABASE_URL.lower():
                raise ValueError(
                    f"{env.capitalize()} database must use PostgreSQL with PostGIS. SQLite is strictly prohibited."
                )
            # 2. JWT: strong non-default secret, minimum 32 chars
            insecure_secrets = [
                "secret",
                "dev_secret_key_change_in_production",
                "changeme",
                "default_jwt_secret_key_32chars!!",
                "",
            ]
            if (
                self.JWT_SECRET_KEY in insecure_secrets
                or len(self.JWT_SECRET_KEY) < 32
                or "dev_secret" in self.JWT_SECRET_KEY.lower()
            ):
                raise ValueError(
                    f"Insecure or weak JWT_SECRET_KEY detected in {env} environment (minimum 32 characters, non-default required)."
                )
            # 3. Redis: Valid Redis URL required
            if not self.REDIS_URL or not (
                self.REDIS_URL.startswith("redis://") or self.REDIS_URL.startswith("rediss://")
            ):
                raise ValueError(
                    f"A valid REDIS_URL (redis:// or rediss://) is required in {env} environment."
                )
            # 4. CORS: Explicit origin required for HTTP services, wildcard prohibited
            if proc in ("api", "web", "all"):
                if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
                    raise ValueError(
                        f"Explicit CORS_ORIGINS must be configured in {env} environment. Wildcard '*' is prohibited for credentialed requests."
                    )
            # 5. S3 Storage: All credentials and bucket required when STORAGE_PROVIDER=s3
            if self.STORAGE_PROVIDER.lower() == "s3" and proc in ("api", "web", "worker", "all"):
                if not (
                    self.AWS_ACCESS_KEY_ID
                    and self.AWS_SECRET_ACCESS_KEY
                    and self.AWS_REGION
                    and self.S3_BUCKET_NAME
                ):
                    raise ValueError(
                        "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, and S3_BUCKET_NAME are all required when STORAGE_PROVIDER=s3."
                    )
            # 6. Firebase Validation
            if self.FIREBASE_CREDENTIALS_JSON:
                import json
                try:
                    parsed = json.loads(self.FIREBASE_CREDENTIALS_JSON)
                    if not isinstance(parsed, dict):
                        raise ValueError("FIREBASE_CREDENTIALS_JSON must be a valid JSON object.")
                except Exception as e:
                    if isinstance(e, ValueError) and "must be a valid JSON object" in str(e):
                        raise
                    raise ValueError("FIREBASE_CREDENTIALS_JSON contains invalid or unparseable JSON.")

            if self.FIREBASE_CREDENTIALS_PATH and not os.path.exists(self.FIREBASE_CREDENTIALS_PATH):
                raise ValueError(
                    f"FIREBASE_CREDENTIALS_PATH specified ({self.FIREBASE_CREDENTIALS_PATH}) but file not found."
                )

            if self.REQUIRE_FIREBASE:
                if not self.FIREBASE_CREDENTIALS_JSON and not self.FIREBASE_CREDENTIALS_PATH:
                    raise ValueError(
                        "REQUIRE_FIREBASE is enabled but neither FIREBASE_CREDENTIALS_JSON nor FIREBASE_CREDENTIALS_PATH is configured."
                    )
            # 7. AI Triage Safety: Mock provider strictly forbidden in production and staging
            if self.AI_TRIAGE_PROVIDER.lower() == "mock":
                raise ValueError(
                    f"Mock AI triage provider is strictly prohibited in {env} environment."
                )
        return self
    
    class Config:
        env_file = ".env"

settings = Settings()

