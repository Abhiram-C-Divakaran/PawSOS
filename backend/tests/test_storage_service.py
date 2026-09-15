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


def test_aws_s3_works_without_s3_endpoint_url():
    """Verify AWS S3 initializes normally without endpoint_url when S3_ENDPOINT_URL is empty."""
    from app.services.storage_service import S3StorageProvider
    with patch("boto3.client") as mock_boto:
        with patch.object(settings, "S3_ENDPOINT_URL", ""):
            with patch.object(settings, "AWS_ACCESS_KEY_ID", "test_ak"):
                with patch.object(settings, "AWS_SECRET_ACCESS_KEY", "test_sk"):
                    with patch.object(settings, "AWS_REGION", "ap-south-1"):
                        with patch.object(settings, "S3_BUCKET_NAME", "mybucket"):
                            provider = S3StorageProvider()
                            assert provider.bucket == "mybucket"
                            # Verify endpoint_url was NOT passed to boto3
                            mock_boto.assert_called_once()
                            call_kwargs = mock_boto.call_args[1]
                            assert "endpoint_url" not in call_kwargs
                            assert call_kwargs["region_name"] == "ap-south-1"
                            assert call_kwargs["aws_access_key_id"] == "test_ak"
                            assert call_kwargs["aws_secret_access_key"] == "test_sk"


def test_custom_s3_endpoint_passed_to_boto3():
    """Verify custom S3 endpoint URL and path-style addressing are passed to boto3 when configured."""
    from app.services.storage_service import S3StorageProvider
    custom_endpoint = "https://test-ref.supabase.co/storage/v1/s3"
    with patch("boto3.client") as mock_boto:
        with patch.object(settings, "S3_ENDPOINT_URL", custom_endpoint):
            with patch.object(settings, "AWS_ACCESS_KEY_ID", "supabase_ak"):
                with patch.object(settings, "AWS_SECRET_ACCESS_KEY", "supabase_sk"):
                    with patch.object(settings, "AWS_REGION", "ap-south-1"):
                        with patch.object(settings, "S3_BUCKET_NAME", "evidence"):
                            provider = S3StorageProvider()
                            assert provider.bucket == "evidence"
                            mock_boto.assert_called_once()
                            call_kwargs = mock_boto.call_args[1]
                            assert call_kwargs["endpoint_url"] == custom_endpoint
                            assert call_kwargs["aws_access_key_id"] == "supabase_ak"
                            # Check path-style addressing in botocore config
                            assert "config" in call_kwargs
                            cfg = call_kwargs["config"]
                            assert getattr(cfg, "s3", {}).get("addressing_style") == "path"


@pytest.mark.asyncio
async def test_canonical_object_keys_remain_unchanged():
    """Verify upload_image produces stable canonical keys (rescues/uuid.ext) without endpoint or bucket prefixes."""
    from app.services.storage_service import S3StorageProvider, normalize_image_key
    custom_endpoint = "https://test-ref.supabase.co/storage/v1/s3"
    with patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3
        with patch.object(settings, "S3_ENDPOINT_URL", custom_endpoint):
            with patch.object(settings, "S3_BUCKET_NAME", "evidence"):
                provider = S3StorageProvider()
                img_bytes = create_test_image()
                upload = UploadFile(
                    filename="evidence.jpg",
                    file=img_bytes,
                    headers=Headers({"content-type": "image/jpeg"}),
                )
                key = await provider.upload_image(upload)

                # Canonical key MUST start with rescues/ and end with .jpg, NOT a full URL
                assert key.startswith("rescues/")
                assert key.endswith(".jpg")
                assert "http" not in key
                assert "supabase" not in key
                assert "evidence" not in key.split("/")[0]

                # Normalization of full path-style URL returns same canonical key
                full_url = f"{custom_endpoint}/evidence/{key}"
                normalized = normalize_image_key(full_url)
                assert normalized == key


def test_presigned_url_generation_uses_configured_s3_endpoint():
    """Verify presigned URL generation passes canonical key and bucket to client configured with custom endpoint."""
    from app.services.storage_service import S3StorageProvider
    custom_endpoint = "https://test-ref.supabase.co/storage/v1/s3"
    with patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = f"{custom_endpoint}/evidence/rescues/sample.jpg?token=test"
        mock_boto.return_value = mock_s3

        with patch.object(settings, "S3_ENDPOINT_URL", custom_endpoint):
            with patch.object(settings, "S3_BUCKET_NAME", "evidence"):
                provider = S3StorageProvider()

                # Test with canonical key
                url = provider.get_presigned_url("rescues/sample.jpg", expires_in=900)
                assert f"{custom_endpoint}/evidence/rescues/sample.jpg" in url
                mock_s3.generate_presigned_url.assert_called_with(
                    "get_object",
                    Params={"Bucket": "evidence", "Key": "rescues/sample.jpg"},
                    ExpiresIn=900,
                )

                # Test with full custom endpoint URL (should normalize key and generate presigned URL)
                full_custom_url = f"{custom_endpoint}/evidence/rescues/sample.jpg"
                url2 = provider.get_presigned_url(full_custom_url, expires_in=900)
                assert url2 == f"{custom_endpoint}/evidence/rescues/sample.jpg?token=test"
