import io
import os
import uuid
import shutil
import logging
from abc import ABC, abstractmethod
from fastapi import UploadFile
from PIL import Image, ImageOps
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
Image.MAX_IMAGE_PIXELS = 25_000_000  # Image bomb protection ceiling (~25 MP)

MIME_TO_FORMAT = {
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}

def optimize_image(file: UploadFile) -> io.BytesIO:
    """
    Image optimization for evidence photos:
    - Normalizes image orientation using EXIF transpose
    - Resizes dimensions exceeding 2048px using high-quality Lanczos resampling
    - Strips unnecessary EXIF metadata to protect user location/device privacy
    - Validates decoded image format against declared MIME type
    - Rejects malformed, invalid, or bomb images with 400 Bad Request
    """
    file.file.seek(0)
    raw_bytes = file.file.read()
    file.file.seek(0)

    content_type = file.content_type
    expected_format = MIME_TO_FORMAT.get(content_type)
    if not expected_format:
        raise BadRequestException(f"Unsupported image type '{content_type}'.")

    try:
        # Check for image decompression bomb / verify integrity
        check_img = Image.open(io.BytesIO(raw_bytes))
        check_img.verify()
    except Image.DecompressionBombError:
        raise BadRequestException("Image dimensions exceed maximum safe limits (decompression bomb detected).")
    except Exception as e:
        logger.warning(f"Image decode failed: {e}")
        raise BadRequestException("Malformed or unparseable image content.")

    try:
        image = Image.open(io.BytesIO(raw_bytes))
        decoded_format = image.format
        if decoded_format != expected_format:
            if not (expected_format == "JPEG" and decoded_format in ("JPEG", "MPO")):
                raise BadRequestException(
                    f"Image content mismatch: declared '{content_type}' but decoded format is '{decoded_format}'."
                )

        image = ImageOps.exif_transpose(image)
        fmt = expected_format

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
    except Image.DecompressionBombError:
        raise BadRequestException("Image dimensions exceed maximum safe limits.")
    except BadRequestException:
        raise
    except Exception as e:
        logger.warning(f"Image optimization error: {e}")
        raise BadRequestException("Invalid or corrupted image data.")

class BaseStorageProvider(ABC):
    @abstractmethod
    async def upload_image(self, file: UploadFile) -> str:
        pass

    @abstractmethod
    def delete_image(self, url: str) -> bool:
        pass

    @abstractmethod
    def check_health(self) -> bool:
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

    def check_health(self) -> bool:
        return os.path.exists(self.upload_dir) and os.access(self.upload_dir, os.W_OK)

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

    def check_health(self) -> bool:
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
            return True
        except Exception as e:
            logger.warning(f"S3 health check failed: {e}")
            return False

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
    if provider == "s3":
        try:
            return S3StorageProvider()
        except Exception as e:
            if settings.ENVIRONMENT in ["production", "staging"]:
                raise RuntimeError(f"FATAL: S3StorageProvider initialization failed in {settings.ENVIRONMENT}: {e}")
            logger.warning(f"Could not initialize S3 provider ({e}). Falling back to local storage.")
            return LocalStorageProvider()
    return LocalStorageProvider()

storage_service = get_storage_provider()

