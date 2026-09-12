from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./pawsos.db"
    JWT_SECRET_KEY: str = "secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = ""
    ENVIRONMENT: str = "development"

    # Redis & Background Tasks
    REDIS_URL: str = "redis://localhost:6379/0"

    # Cloud Storage (local, s3, cloudinary)
    STORAGE_PROVIDER: str = "local"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # Firebase Cloud Messaging
    FIREBASE_CREDENTIALS_PATH: str = ""
    FIREBASE_PROJECT_ID: str = ""

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

    # Security & Cookie Settings
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    RATE_LIMIT_PER_MINUTE: int = 60
    SENTRY_DSN: str = ""
    
    class Config:
        env_file = ".env"

settings = Settings()
