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

    @abstractmethod
    def get_presigned_url(self, key_or_url: str, expires_in: int = 3600) -> str:
        pass

    @abstractmethod
    def get_image_bytes(self, key_or_url: str, max_bytes: int = MAX_FILE_SIZE_BYTES) -> bytes:
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

    def get_presigned_url(self, key_or_url: str, expires_in: int = 3600) -> str:
        """For local storage, return the URL as is."""
        return key_or_url

    def get_image_bytes(self, key_or_url: str, max_bytes: int = MAX_FILE_SIZE_BYTES) -> bytes:
        """Safely load local image bytes for internal backend processing with size/integrity checks."""
        if not key_or_url:
            raise BadRequestException("Image key or path is required.")
        cleaned = key_or_url.split("?")[0].strip()
        filename = os.path.basename(cleaned)
        filepath = os.path.join(self.upload_dir, filename)
        if not os.path.exists(filepath):
            raise BadRequestException(f"Image not found on storage: {filename}")

        file_size = os.path.getsize(filepath)
        if file_size > max_bytes:
            raise BadRequestException(f"Image size ({file_size} bytes) exceeds maximum limit of {max_bytes} bytes.")

        with open(filepath, "rb") as f:
            raw = f.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise BadRequestException("Image file exceeds maximum allowable bytes.")

        try:
            check_img = Image.open(io.BytesIO(raw))
            check_img.verify()
        except Image.DecompressionBombError:
            raise BadRequestException("Image exceeds safe decompression limits.")
        except Exception as e:
            raise BadRequestException(f"Invalid or corrupted image data: {e}")

        return raw

def normalize_image_key(raw: str | None) -> str | None:
    """
    Normalize raw image reference to a stable canonical storage key or local path.
    Strips query parameters (e.g. AWS presigned tokens) and S3 bucket URL prefixes,
    ensuring only the permanent object reference is persisted in the database.
    """
    if not raw:
        return raw
    cleaned = raw.split("?")[0].strip()

    endpoint = (settings.S3_ENDPOINT_URL or "").rstrip("/")
    if endpoint and cleaned.startswith(endpoint):
        after = cleaned[len(endpoint):].lstrip("/")
        if after.startswith(f"{settings.S3_BUCKET_NAME}/"):
            return after[len(settings.S3_BUCKET_NAME) + 1:]
        return after

    if "amazonaws.com/" in cleaned:
        after = cleaned.split("amazonaws.com/", 1)[1]
        parts = after.split("/", 1)
        if len(parts) == 2 and parts[0] == settings.S3_BUCKET_NAME:
            return parts[1]
        return after
    return cleaned


class S3StorageProvider(BaseStorageProvider):
    def __init__(self):
        import boto3
        from botocore.config import Config

        client_kwargs = {
            "region_name": settings.AWS_REGION or None,
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID or None,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY or None,
        }
        if settings.S3_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL

        s3_config = {}
        if settings.S3_FORCE_PATH_STYLE or settings.S3_ENDPOINT_URL:
            s3_config["addressing_style"] = "path"

        if s3_config:
            client_kwargs["config"] = Config(s3=s3_config)

        self.s3_client = boto3.client("s3", **client_kwargs)
        self.bucket = settings.S3_BUCKET_NAME

    def check_health(self) -> bool:
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
            return True
        except Exception as e:
            logger.warning(f"S3 health check failed: {e}")
            return False

    def get_presigned_url(self, key_or_url: str, expires_in: int = 900) -> str:
        """
        Generate a secure, time-limited presigned GET URL for an evidence image stored in private S3 bucket.
        Protects user/animal location privacy without making the bucket publicly accessible.
        Normalizes both stable object keys (rescues/...) and legacy full S3 URLs.
        Returns external non-S3 URLs or local /uploads/ paths unchanged.
        """
        if not key_or_url:
            return key_or_url

        # Return local storage paths or root-relative paths unchanged
        if key_or_url.startswith("/uploads/") or key_or_url.startswith("/"):
            return key_or_url

        key = key_or_url
        if "?" in key:
            key = key.split("?")[0]

        endpoint = (settings.S3_ENDPOINT_URL or "").rstrip("/")
        if endpoint and key.startswith(endpoint):
            after = key[len(endpoint):].lstrip("/")
            if after.startswith(f"{self.bucket}/"):
                key = after[len(self.bucket) + 1:]
            else:
                key = after

        prefix = f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/"
        alt_prefix = f"https://{self.bucket}.s3.amazonaws.com/"

        if key.startswith(prefix):
            key = key[len(prefix):]
        elif key.startswith(alt_prefix):
            key = key[len(alt_prefix):]
        elif "amazonaws.com/" in key:
            after = key.split("amazonaws.com/", 1)[1]
            if after.startswith(f"{self.bucket}/"):
                key = after[len(self.bucket) + 1:]
            else:
                key = after
        elif key.startswith("http://") or key.startswith("https://"):
            # Non-S3 external URL (e.g. mock tile server or placeholder)
            return key_or_url

        try:
            duration = expires_in or settings.S3_PRESIGNED_URL_EXPIRE_SECONDS
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=duration,
            )
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {key}: {e}")
            return key_or_url

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
            # Return stable canonical object key, NOT direct public URL
            return filename
        except Exception as e:
            logger.error(f"S3 upload failure: {e}")
            raise BadRequestException("Cloud storage upload failed.")

    def delete_image(self, url_or_key: str) -> bool:
        try:
            key = normalize_image_key(url_or_key) or url_or_key
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            logger.error(f"S3 delete error: {e}")
            return False

    def get_image_bytes(self, key_or_url: str, max_bytes: int = MAX_FILE_SIZE_BYTES) -> bytes:
        """Safely load S3 image bytes by canonical key for internal backend processing with size/integrity checks."""
        if not key_or_url:
            raise BadRequestException("Image key or URL is required.")
        key = normalize_image_key(key_or_url) or key_or_url
        if not key:
            raise BadRequestException("Invalid S3 object key.")

        try:
            head = self.s3_client.head_object(Bucket=self.bucket, Key=key)
            size = head.get("ContentLength", 0)
            if size > max_bytes:
                raise BadRequestException(f"S3 image object ({size} bytes) exceeds maximum limit of {max_bytes} bytes.")

            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            raw = response["Body"].read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise BadRequestException("S3 image object exceeds maximum allowable bytes.")
        except BadRequestException:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch image from S3: {e}")
            raise BadRequestException(f"Could not retrieve image from storage: {e}")

        try:
            check_img = Image.open(io.BytesIO(raw))
            check_img.verify()
        except Image.DecompressionBombError:
            raise BadRequestException("Image exceeds safe decompression limits.")
        except Exception as e:
            raise BadRequestException(f"Invalid or corrupted image data: {e}")

        return raw

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

