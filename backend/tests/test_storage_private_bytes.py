import io
import os
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
from app.services.storage_service import LocalStorageProvider, S3StorageProvider
from app.core.exceptions import BadRequestException
from app.config import settings

def test_local_storage_get_image_bytes(tmp_path):
    provider = LocalStorageProvider(upload_dir=str(tmp_path))

    # Create a small valid test PNG image
    img = Image.new("RGB", (100, 100), color="blue")
    img_filename = "test_dog.png"
    img_path = tmp_path / img_filename
    img.save(str(img_path))

    data = provider.get_image_bytes(img_filename)
    assert len(data) > 0
    assert data[:8] == b"\x89PNG\r\n\x1a\n"

def test_local_storage_get_image_bytes_not_found(tmp_path):
    provider = LocalStorageProvider(upload_dir=str(tmp_path))

    with pytest.raises(BadRequestException) as exc_info:
        provider.get_image_bytes("non_existent_image.jpg")
    assert "Image not found on storage" in str(exc_info.value)

def test_local_storage_get_image_bytes_exceeds_max_size(tmp_path):
    provider = LocalStorageProvider(upload_dir=str(tmp_path))

    big_file = tmp_path / "big_image.bin"
    big_file.write_bytes(b"A" * 2000)

    with pytest.raises(BadRequestException) as exc_info:
        provider.get_image_bytes("big_image.bin", max_bytes=1000)
    assert "exceeds maximum limit" in str(exc_info.value)

def test_s3_storage_get_image_bytes():
    # Valid PNG bytes in memory
    buf = io.BytesIO()
    valid_img = Image.new("RGB", (50, 50), color="red")
    valid_img.save(buf, format="PNG")
    valid_png_bytes = buf.getvalue()

    with patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = valid_png_bytes
        mock_s3.head_object.return_value = {"ContentLength": len(valid_png_bytes)}
        mock_s3.get_object.return_value = {
            "Body": mock_body,
            "ContentLength": len(valid_png_bytes),
        }
        mock_boto.return_value = mock_s3

        with patch.object(settings, "S3_BUCKET_NAME", "pawsos-test-bucket"):
            provider = S3StorageProvider()
            data = provider.get_image_bytes("rescues/cat.png", max_bytes=len(valid_png_bytes) + 100)

            assert data == valid_png_bytes
            mock_s3.head_object.assert_called_once_with(
                Bucket="pawsos-test-bucket",
                Key="rescues/cat.png"
            )
            mock_s3.get_object.assert_called_once_with(
                Bucket="pawsos-test-bucket",
                Key="rescues/cat.png"
            )

def test_s3_storage_get_image_bytes_exceeds_content_length():
    with patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_s3.head_object.return_value = {
            "ContentLength": 50000000, # 50 MB
        }
        mock_boto.return_value = mock_s3

        with patch.object(settings, "S3_BUCKET_NAME", "pawsos-test-bucket"):
            provider = S3StorageProvider()
            with pytest.raises(BadRequestException) as exc_info:
                provider.get_image_bytes("rescues/huge.png", max_bytes=10000000) # 10 MB limit
            assert "exceeds maximum limit" in str(exc_info.value)

def test_storage_empty_key_rejected(tmp_path):
    provider = LocalStorageProvider(upload_dir=str(tmp_path))
    with pytest.raises(BadRequestException):
        provider.get_image_bytes("")

def test_s3_storage_get_image_bytes_corrupted_data():
    with patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = b"corrupted_non_image_bytes_12345"
        mock_s3.head_object.return_value = {"ContentLength": 32}
        mock_s3.get_object.return_value = {
            "Body": mock_body,
            "ContentLength": 32,
        }
        mock_boto.return_value = mock_s3

        with patch.object(settings, "S3_BUCKET_NAME", "pawsos-test-bucket"):
            provider = S3StorageProvider()
            with pytest.raises(BadRequestException) as exc_info:
                provider.get_image_bytes("rescues/corrupt.png")
            assert "Invalid or corrupted image data" in str(exc_info.value)

