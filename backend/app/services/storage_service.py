import io
import os
import uuid
import shutil
import logging
from abc import ABC, abstractmethod
from fastapi import UploadFile
from PIL import Image
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
MAX_IMAGE_DIMENSION = 2048

def optimize_image(file: UploadFile) -> io.BytesIO:
    """
    Image optimization for evidence photos:
    - Resizes dimensions exceeding 2048px using high-quality Lanczos resampling
    - Strips unnecessary EXIF metadata to protect user location/device privacy
    - Compresses without noticeable loss of forensic evidence quality
    """
    file.file.seek(0)
    raw_bytes = file.file.read()
    file.file.seek(0)

    try:
        image = Image.open(io.BytesIO(raw_bytes))
        content_type = file.content_type
        fmt = "JPEG" if content_type in ["image/jpeg", "image/jpg"] else ("WEBP" if content_type == "image/webp" else "PNG")

        if fmt == "JPEG" and image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Resize down to max dimension if needed
        if image.width > MAX_IMAGE_DIMENSION or image.height > MAX_IMAGE_DIMENSION:
            image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        if fmt == "JPEG":
            image.save(buffer, format="JPEG", quality=85, optimize=True)
        elif fmt == "WEBP":
            image.save(buffer, format="WEBP", quality=85)
        else:
            image.save(buffer, format="PNG", optimize=True)

        buffer.seek(0)
        return buffer
    except Exception as e:
        logger.warning(f"Image optimization error ({e}); falling back to raw upload.")
        return io.BytesIO(raw_bytes)

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

        optimized_stream = optimize_image(file)

        ext = ALLOWED_MIME_TYPES[content_type]
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(self.upload_dir, filename)

        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(optimized_stream, buffer)

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
        self.bucket = settings.S3_BUCKET_NAME

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
            raise BadRequestException("Image size exceeds maximum limit of 10 MB.")

        optimized_stream = optimize_image(file)

        ext = ALLOWED_MIME_TYPES[content_type]
        filename = f"rescues/{uuid.uuid4().hex}{ext}"

        try:
            self.s3_client.upload_fileobj(
                optimized_stream,
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
    if provider == "s3" and settings.S3_BUCKET_NAME:
        try:
            return S3StorageProvider()
        except Exception as e:
            logger.warning(f"Could not initialize S3 provider ({e}). Falling back to local storage.")
            return LocalStorageProvider()
    return LocalStorageProvider()

storage_service = get_storage_provider()
