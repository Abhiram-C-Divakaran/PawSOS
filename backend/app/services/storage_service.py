import os
import uuid
import shutil
import logging
from abc import ABC, abstractmethod
from fastapi import UploadFile
from app.config import settings
from app.core.exceptions import BadRequestException

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

class BaseStorageProvider(ABC):
    @abstractmethod
    async def upload_image(self, file: UploadFile) -> str:
        pass

    @abstractmethod
    def delete_image(self, url: str) -> bool:
        pass

class LocalStorageProvider(BaseStorageProvider):
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    async def upload_image(self, file: UploadFile) -> str:
        content_type = file.content_type
        if content_type not in ALLOWED_MIME_TYPES:
            raise BadRequestException(
                f"Unsupported image type '{content_type}'. Allowed types: JPG, PNG, WEBP."
            )

        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)
        if size > MAX_FILE_SIZE_BYTES:
            raise BadRequestException(
                f"Image size ({size / (1024*1024):.1f} MB) exceeds maximum limit of 10 MB."
            )

        # Generate unique random filename to prevent directory traversal or malicious names
        ext = ALLOWED_MIME_TYPES[content_type]
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(self.upload_dir, filename)

        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return f"/uploads/{filename}"

    def delete_image(self, url: str) -> bool:
        if not url.startswith("/uploads/"):
            return False
        filename = os.path.basename(url)
        filepath = os.path.join(self.upload_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

class S3StorageProvider(BaseStorageProvider):
    def __init__(self):
        import boto3
        self.s3_client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.bucket = settings.AWS_S3_BUCKET

    async def upload_image(self, file: UploadFile) -> str:
        content_type = file.content_type
        if content_type not in ALLOWED_MIME_TYPES:
            raise BadRequestException(
                f"Unsupported image type '{content_type}'. Allowed types: JPG, PNG, WEBP."
            )

        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)
        if size > MAX_FILE_SIZE_BYTES:
            raise BadRequestException(
                f"Image size exceeds maximum limit of 10 MB."
            )

        ext = ALLOWED_MIME_TYPES[content_type]
        filename = f"rescues/{uuid.uuid4().hex}{ext}"

        try:
            self.s3_client.upload_fileobj(
                file.file,
                self.bucket,
                filename,
                ExtraArgs={"ContentType": content_type}
            )
            return f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{filename}"
        except Exception as e:
            logger.error(f"S3 upload failure: {e}")
            raise BadRequestException("Cloud storage upload failed.")

    def delete_image(self, url: str) -> bool:
        try:
            key = url.split(f"{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/")[-1]
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            logger.error(f"S3 delete error: {e}")
            return False

def get_storage_provider() -> BaseStorageProvider:
    provider = settings.STORAGE_PROVIDER.lower()
    if provider == "s3" and settings.AWS_S3_BUCKET:
        try:
            return S3StorageProvider()
        except Exception as e:
            logger.warning(f"Could not initialize S3 provider ({e}). Falling back to local storage.")
            return LocalStorageProvider()
    return LocalStorageProvider()

storage_service = get_storage_provider()
