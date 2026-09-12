import io
import pytest
from PIL import Image
from fastapi import UploadFile
from starlette.datastructures import Headers
from unittest.mock import patch, MagicMock

from app.services.storage_service import (
    optimize_image,
    LocalStorageProvider,
    get_storage_provider,
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
)
from app.core.exceptions import BadRequestException
from app.config import settings

def create_test_image(format="JPEG", size=(100, 100), color="red"):
    file_bytes = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(file_bytes, format=format)
    file_bytes.seek(0)
    return file_bytes

@pytest.mark.asyncio
async def test_optimize_image_resizes_large_dimensions():
    large_bytes = create_test_image(size=(3000, 2000))
    upload = UploadFile(
        filename="large.jpg",
        file=large_bytes,
        headers=Headers({"content-type": "image/jpeg"})
    )

    optimized = optimize_image(upload)
    result_img = Image.open(optimized)

    assert result_img.width <= 2048
    assert result_img.height <= 2048

@pytest.mark.asyncio
async def test_local_storage_provider_upload_and_delete(tmp_path):
    provider = LocalStorageProvider(upload_dir=str(tmp_path))

    img_bytes = create_test_image()
    upload = UploadFile(
        filename="photo.jpg",
        file=img_bytes,
        headers=Headers({"content-type": "image/jpeg"})
    )

    url = await provider.upload_image(upload)
    assert url.startswith("/uploads/")
    assert url.endswith(".jpg")

    deleted = provider.delete_image(url)
    assert deleted is True

@pytest.mark.asyncio
async def test_storage_rejects_invalid_mime_type(tmp_path):
    provider = LocalStorageProvider(upload_dir=str(tmp_path))

    dummy = io.BytesIO(b"%PDF-1.4...")
    upload = UploadFile(
        filename="doc.pdf",
        file=dummy,
        headers=Headers({"content-type": "application/pdf"})
    )

    with pytest.raises(BadRequestException) as exc_info:
        await provider.upload_image(upload)
    assert "Unsupported image type" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_storage_rejects_oversized_file(tmp_path):
    provider = LocalStorageProvider(upload_dir=str(tmp_path))

    mock_file = MagicMock()
    mock_file.tell.return_value = 11 * 1024 * 1024
    upload = UploadFile(
        filename="huge.jpg",
        file=mock_file,
        headers=Headers({"content-type": "image/jpeg"})
    )

    with pytest.raises(BadRequestException) as exc_info:
        await provider.upload_image(upload)
    assert "exceeds maximum limit" in str(exc_info.value.detail)

def test_s3_failfast_in_staging_or_production():
    with patch.object(settings, "STORAGE_PROVIDER", "s3"):
        with patch.object(settings, "ENVIRONMENT", "production"):
            with patch("boto3.client", side_effect=Exception("AWS credentials missing")):
                with pytest.raises(RuntimeError) as exc_info:
                    get_storage_provider()
                assert "FATAL: S3StorageProvider initialization failed" in str(exc_info.value)

def test_s3_fallback_in_development():
    with patch.object(settings, "STORAGE_PROVIDER", "s3"):
        with patch.object(settings, "ENVIRONMENT", "development"):
            with patch("boto3.client", side_effect=Exception("AWS credentials missing")):
                provider = get_storage_provider()
                assert isinstance(provider, LocalStorageProvider)

def test_storage_rejects_malformed_bytes():
    corrupt_stream = io.BytesIO(b"this is completely corrupted binary data")
    upload = UploadFile(
        filename="corrupted.jpg",
        file=corrupt_stream,
        headers=Headers({"content-type": "image/jpeg"})
    )
    with pytest.raises(BadRequestException) as exc_info:
        optimize_image(upload)
    assert "Malformed or unparseable" in str(exc_info.value.detail) or "Invalid or corrupted" in str(exc_info.value.detail)

def test_storage_rejects_format_mismatch():
    # PNG bytes claiming to be JPEG
    png_bytes = create_test_image(format="PNG")
    upload = UploadFile(
        filename="fake.jpg",
        file=png_bytes,
        headers=Headers({"content-type": "image/jpeg"})
    )
    with pytest.raises(BadRequestException) as exc_info:
        optimize_image(upload)
    assert "Image content mismatch" in str(exc_info.value.detail)

def test_storage_rejects_decompression_bomb():
    img_bytes = create_test_image(size=(100, 100))
    upload = UploadFile(
        filename="bomb.jpg",
        file=img_bytes,
        headers=Headers({"content-type": "image/jpeg"})
    )
    with patch("PIL.Image.open", side_effect=Image.DecompressionBombError("Bomb detected")):
        with pytest.raises(BadRequestException) as exc_info:
            optimize_image(upload)
        assert "decompression bomb detected" in str(exc_info.value.detail)
