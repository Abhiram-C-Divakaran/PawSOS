"""Test suite for private S3 storage representation and authorized evidence-image access.
Tests presigned URL generation, URL expiration, canonical key persistence in DB,
and multi-tenant / multi-role access authorization guards.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.config import settings
from app.models.user import User
from app.models.rescue_case import RescueCase
from app.models.animal_image import AnimalImage
from app.models.organization import Organization
from app.models.veterinary_facility import VeterinaryFacility
from app.models.rescue_assignment import RescueAssignment
from app.core.constants import UserRole, RescueStatus, AssignmentStatus, OrganizationType
from app.core.security import get_password_hash, create_access_token
from app.services.storage_service import (
    S3StorageProvider,
    normalize_image_key,
    get_storage_provider,
)


class TestS3MediaProviderUnit:
    """Unit tests for S3 storage provider presigned URL generation and key normalization."""

    def test_normalize_image_key_cleans_urls(self):
        # Raw key
        assert normalize_image_key("rescues/abc.jpg") == "rescues/abc.jpg"
        # Signed URL with query tokens
        signed = "https://mybucket.s3.ap-south-1.amazonaws.com/rescues/abc.jpg?AWSAccessKeyId=AKIA&Signature=XYZ"
        with patch.object(settings, "S3_BUCKET_NAME", "mybucket"):
            assert normalize_image_key(signed) == "rescues/abc.jpg"
        # Local upload path
        assert normalize_image_key("/uploads/sample.jpg") == "/uploads/sample.jpg"

    def test_s3_presigned_url_generation(self):
        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/mybucket/rescues/1.jpg?token=secret"
            mock_boto.return_value = mock_s3

            with patch.object(settings, "S3_BUCKET_NAME", "mybucket"):
                with patch.object(settings, "AWS_REGION", "ap-south-1"):
                    provider = S3StorageProvider()
                    url = provider.get_presigned_url("rescues/1.jpg", expires_in=900)

                    assert "token=secret" in url
                    mock_s3.generate_presigned_url.assert_called_once_with(
                        "get_object",
                        Params={"Bucket": "mybucket", "Key": "rescues/1.jpg"},
                        ExpiresIn=900,
                    )

    def test_s3_presigned_url_with_legacy_full_url(self):
        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/mybucket/rescues/2.jpg?token=signed"
            mock_boto.return_value = mock_s3

            with patch.object(settings, "S3_BUCKET_NAME", "mybucket"):
                with patch.object(settings, "AWS_REGION", "ap-south-1"):
                    provider = S3StorageProvider()
                    legacy_url = "https://mybucket.s3.ap-south-1.amazonaws.com/rescues/2.jpg"
                    url = provider.get_presigned_url(legacy_url, expires_in=600)

                    assert "token=signed" in url
                    mock_s3.generate_presigned_url.assert_called_once_with(
                        "get_object",
                        Params={"Bucket": "mybucket", "Key": "rescues/2.jpg"},
                        ExpiresIn=600,
                    )

    def test_s3_presigned_url_external_url_untouched(self):
        with patch("boto3.client") as mock_boto:
            provider = S3StorageProvider()
            ext_url = "https://images.unsplash.com/photo-12345"
            assert provider.get_presigned_url(ext_url) == ext_url

    def test_s3_presigned_url_handles_client_error_gracefully(self):
        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.side_effect = Exception("AWS STS error")
            mock_boto.return_value = mock_s3

            provider = S3StorageProvider()
            fallback = provider.get_presigned_url("rescues/err.jpg")
            assert fallback == "rescues/err.jpg"


class TestEvidenceImageAccessAuthorization:
    """Integration test suite verifying multi-tenant and role-based access to evidence images."""

    @pytest.fixture
    def setup_case_and_users(self, db):
        # 1. Create Organization Alpha and Beta
        org_a = Organization(
            name="Org Alpha",
            organization_type=OrganizationType.NGO,
            email="admin@orga.org",
            phone="+919800000001",
            address="Kochi",
            verification_status=True,
        )
        org_b = Organization(
            name="Org Beta",
            organization_type=OrganizationType.NGO,
            email="admin@orgb.org",
            phone="+919800000002",
            address="Kochi",
            verification_status=True,
        )
        db.add_all([org_a, org_b])
        db.commit()

        # 2. Create Veterinary Facilities
        fac_a = VeterinaryFacility(
            name="PetCare Clinic A",
            organization_id=org_a.id,
            address="Kochi Marine Drive",
            phone="+919800000010",
            latitude=9.9816,
            longitude=76.2799,
            location="POINT(76.2799 9.9816)",
            is_verified=True,
        )
        fac_b = VeterinaryFacility(
            name="PetCare Clinic B",
            organization_id=org_b.id,
            address="Fort Kochi",
            phone="+919800000020",
            latitude=9.9650,
            longitude=76.2420,
            location="POINT(76.2420 9.9650)",
            is_verified=True,
        )
        db.add_all([fac_a, fac_b])
        db.commit()

        # 3. Create Users
        # Citizen Reporter
        reporter = User(
            full_name="Citizen Reporter",
            email=f"reporter_{uuid.uuid4().hex[:6]}@example.com",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
            password_hash=get_password_hash("pass123"),
            role=UserRole.CITIZEN,
            is_active=True,
        )
        # Unrelated Citizen
        other_citizen = User(
            full_name="Other Citizen",
            email=f"other_{uuid.uuid4().hex[:6]}@example.com",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
            password_hash=get_password_hash("pass123"),
            role=UserRole.CITIZEN,
            is_active=True,
        )
        # Assigned Rescuer
        assigned_rescuer = User(
            full_name="Assigned Rescuer",
            email=f"rescuer_{uuid.uuid4().hex[:6]}@example.com",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
            password_hash=get_password_hash("pass123"),
            role=UserRole.RESCUER,
            organization_id=org_a.id,
            is_active=True,
        )
        # Unassigned Rescuer
        unassigned_rescuer = User(
            full_name="Unassigned Rescuer",
            email=f"other_rescuer_{uuid.uuid4().hex[:6]}@example.com",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
            password_hash=get_password_hash("pass123"),
            role=UserRole.RESCUER,
            organization_id=org_b.id,
            is_active=True,
        )
        # NGO Admin A (Authorized)
        ngo_admin_a = User(
            full_name="NGO Admin A",
            email=f"admin_a_{uuid.uuid4().hex[:6]}@example.com",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
            password_hash=get_password_hash("pass123"),
            role=UserRole.NGO_ADMIN,
            organization_id=org_a.id,
            is_active=True,
        )
        # NGO Admin B (Cross-Tenant)
        ngo_admin_b = User(
            full_name="NGO Admin B",
            email=f"admin_b_{uuid.uuid4().hex[:6]}@example.com",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
            password_hash=get_password_hash("pass123"),
            role=UserRole.NGO_ADMIN,
            organization_id=org_b.id,
            is_active=True,
        )
        # Vet Facility A (Authorized)
        vet_a = User(
            full_name="Vet A",
            email=f"vet_a_{uuid.uuid4().hex[:6]}@example.com",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
            password_hash=get_password_hash("pass123"),
            role=UserRole.VETERINARIAN,
            veterinary_facility_id=fac_a.id,
            is_active=True,
        )
        # Vet Facility B (Unrelated Facility)
        vet_b = User(
            full_name="Vet B",
            email=f"vet_b_{uuid.uuid4().hex[:6]}@example.com",
            phone=f"+9198{uuid.uuid4().hex[:8]}",
            password_hash=get_password_hash("pass123"),
            role=UserRole.VETERINARIAN,
            veterinary_facility_id=fac_b.id,
            is_active=True,
        )

        db.add_all([
            reporter, other_citizen, assigned_rescuer, unassigned_rescuer,
            ngo_admin_a, ngo_admin_b, vet_a, vet_b
        ])
        db.commit()

        # 4. Create Rescue Case referred to Vet Clinic A
        case = RescueCase(
            case_number=f"PR-{uuid.uuid4().hex[:6].upper()}",
            reporter_id=reporter.id,
            organization_id=org_a.id,
            veterinary_facility_id=fac_a.id,
            status=RescueStatus.UNDER_TREATMENT,
            species="Canine",
            description="Injured stray dog",
            latitude=9.9816,
            longitude=76.2799,
            location="POINT(76.2799 9.9816)",
            bleeding=True,
            conscious=True,
            can_walk=False,
            triage_score=85,
        )
        db.add(case)
        db.commit()
        db.refresh(case)

        # 5. Add Assignment
        assignment = RescueAssignment(
            rescue_case_id=case.id,
            rescuer_id=assigned_rescuer.id,
            assignment_status=AssignmentStatus.ACCEPTED,
            accepted_at=datetime.now(timezone.utc),
        )
        db.add(assignment)

        # 6. Add Evidence Image with stable canonical key
        image = AnimalImage(
            rescue_case_id=case.id,
            image_url="rescues/evidence_secret_photo.jpg",
            image_type="REPORT",
            uploaded_by=reporter.id,
        )
        db.add(image)
        db.commit()
        db.refresh(image)

        return {
            "case": case,
            "image": image,
            "reporter": reporter,
            "other_citizen": other_citizen,
            "assigned_rescuer": assigned_rescuer,
            "unassigned_rescuer": unassigned_rescuer,
            "ngo_admin_a": ngo_admin_a,
            "ngo_admin_b": ngo_admin_b,
            "vet_a": vet_a,
            "vet_b": vet_b,
        }

    def test_citizen_reporter_can_access_own_case_image(self, client, setup_case_and_users):
        ctx = setup_case_and_users
        token = create_access_token(ctx["reporter"].id)
        resp = client.get(
            f"/api/v1/rescues/{ctx['case'].id}/images/{ctx['image'].id}/access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "url" in data
        assert data["expires_in"] == 900

    def test_unrelated_citizen_cannot_access_case_image(self, client, setup_case_and_users):
        ctx = setup_case_and_users
        token = create_access_token(ctx["other_citizen"].id)
        resp = client.get(
            f"/api/v1/rescues/{ctx['case'].id}/images/{ctx['image'].id}/access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "Citizens can only access their own reported rescue cases" in resp.text

    def test_assigned_responder_can_access_case_image(self, client, setup_case_and_users):
        ctx = setup_case_and_users
        token = create_access_token(ctx["assigned_rescuer"].id)
        resp = client.get(
            f"/api/v1/rescues/{ctx['case'].id}/images/{ctx['image'].id}/access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "url" in resp.json()

    def test_authorized_ngo_admin_can_access_own_case_image(self, client, setup_case_and_users):
        ctx = setup_case_and_users
        token = create_access_token(ctx["ngo_admin_a"].id)
        resp = client.get(
            f"/api/v1/rescues/{ctx['case'].id}/images/{ctx['image'].id}/access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "url" in resp.json()

    def test_cross_tenant_ngo_admin_cannot_access_case_image(self, client, setup_case_and_users):
        ctx = setup_case_and_users
        token = create_access_token(ctx["ngo_admin_b"].id)
        resp = client.get(
            f"/api/v1/rescues/{ctx['case'].id}/images/{ctx['image'].id}/access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "Cross-tenant access forbidden" in resp.text

    def test_authorized_veterinarian_can_access_assigned_case_image(self, client, setup_case_and_users):
        ctx = setup_case_and_users
        token = create_access_token(ctx["vet_a"].id)
        resp = client.get(
            f"/api/v1/rescues/{ctx['case'].id}/images/{ctx['image'].id}/access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert "url" in resp.json()

    def test_unrelated_veterinarian_cannot_access_case_image(self, client, setup_case_and_users):
        ctx = setup_case_and_users
        token = create_access_token(ctx["vet_b"].id)
        resp = client.get(
            f"/api/v1/rescues/{ctx['case'].id}/images/{ctx['image'].id}/access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "Veterinarians can only view cases assigned to their authorized facility" in resp.text

    def test_image_url_in_database_is_never_signed(self, db, setup_case_and_users):
        """Verify that the database stores only the stable canonical key, never expiring presigned tokens."""
        ctx = setup_case_and_users
        img_record = db.query(AnimalImage).filter(AnimalImage.id == ctx["image"].id).first()
        assert img_record.image_url == "rescues/evidence_secret_photo.jpg"
        assert "?" not in img_record.image_url
        assert "AWSAccessKeyId" not in img_record.image_url
