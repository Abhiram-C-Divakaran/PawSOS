"""Staging Seed Data Script for PawReach Pilot Testing.

Creates two distinct staging NGO organizations (Org Alpha & Org Beta), partner
veterinary facilities, and designated test accounts for cross-tenant pilot
validation. Requires STAGING_SEED_PASSWORD.

Normal seed mode remains create-if-missing. Operator reconciliation mode is
enabled only with STAGING_RECONCILE_EXISTING=true and ENVIRONMENT=staging; in
that mode existing canonical staging users are normalized to the current
fixture, their passwords are rotated, rescuer profiles are reconciled, and
active refresh sessions are revoked.
"""
import sys
import os
from datetime import datetime, timezone

# Add parent directory to sys.path so app modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import inspect
from app.database import SessionLocal, engine
from app.config import settings
from app.models.organization import Organization
from app.models.veterinary_facility import VeterinaryFacility
from app.models.user import User
from app.models.rescuer_profile import RescuerProfile
from app.models.refresh_session import RefreshSession
from app.core.security import get_password_hash
from app.core.constants import UserRole, RescuerAvailability, OrganizationType


INSECURE_PATTERNS = [
    "stagingpass",
    "password",
    "admin123",
    "changeme",
    "pawsos",
    "pawreach",
    "12345678",
]

RECONCILE_ENV_VAR = "STAGING_RECONCILE_EXISTING"


def validate_staging_password(password: str | None) -> str:
    """Validate that the staging seed password meets strict security criteria."""
    if not password:
        raise RuntimeError(
            "STAGING_SEED_PASSWORD environment variable is required to run seed_staging.py. "
            "Please provide a strong, non-default password of at least 14 characters."
        )
    if len(password) < 14:
        raise ValueError(
            f"STAGING_SEED_PASSWORD must be at least 14 characters long (provided: {len(password)})."
        )

    pwd_lower = password.lower()
    for pattern in INSECURE_PATTERNS:
        if pattern in pwd_lower:
            raise ValueError(
                f"STAGING_SEED_PASSWORD contains insecure or common pattern '{pattern}'. "
                "Provide a strong, unpredictable password for staging seeding."
            )
    return password


def is_reconciliation_enabled() -> bool:
    return os.environ.get(RECONCILE_ENV_VAR, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def validate_reconciliation_environment(environment: str, reconcile_existing: bool) -> None:
    """Permit mutation of existing staging identities only in staging."""
    if reconcile_existing and environment != "staging":
        raise RuntimeError(
            "Staging identity reconciliation is permitted only when ENVIRONMENT=staging."
        )


def validate_staging_identity_collision(
    *,
    expected_email: str,
    expected_phone: str,
    existing_by_email: User | None,
    existing_by_phone: User | None,
) -> None:
    """Refuse to overwrite a different identity that owns a reserved seed phone."""
    if (
        existing_by_email is not None
        and existing_by_phone is not None
        and existing_by_email.id != existing_by_phone.id
    ):
        raise RuntimeError(
            "Staging seed identity collision: canonical email and reserved phone "
            f"belong to different users for {expected_email} / {expected_phone}."
        )

    if existing_by_phone is not None and existing_by_phone.email != expected_email:
        raise RuntimeError(
            "Staging seed identity collision: reserved phone "
            f"{expected_phone} is already owned by another user. Refusing reconciliation."
        )


def seed_staging_database():
    env = (os.environ.get("ENVIRONMENT") or settings.ENVIRONMENT or "").lower()
    if env == "production":
        raise RuntimeError(
            "FATAL: Staging seeding is strictly prohibited in production environments (ENVIRONMENT=production)."
        )

    reconcile_existing = is_reconciliation_enabled()
    validate_reconciliation_environment(env, reconcile_existing)

    staging_pwd = validate_staging_password(os.environ.get("STAGING_SEED_PASSWORD"))

    inspector = inspect(engine)
    required_tables = [
        "organizations",
        "veterinary_facilities",
        "users",
        "rescuer_profiles",
        "refresh_sessions",
    ]
    missing = [tbl for tbl in required_tables if not inspector.has_table(tbl)]
    if missing:
        raise RuntimeError(
            f"Database schema not initialized. Missing tables: {missing}. "
            "The staging seed script does not create or mutate schema. "
            "Please run 'alembic upgrade head' before running seed_staging.py."
        )

    mode = "reconciliation" if reconcile_existing else "create-if-missing seed"
    print(f"Running PawReach staging {mode} with validated credentials...")
    db = SessionLocal()

    try:
        org_alpha = (
            db.query(Organization)
            .filter(Organization.name == "Organization Alpha - Stray Relief")
            .first()
        )
        if not org_alpha:
            org_alpha = Organization(
                name="Organization Alpha - Stray Relief",
                organization_type=OrganizationType.NGO,
                address="Marine Drive, Ernakulam, Kerala 682031",
                email="contact@alpha.staging.pawsos.org",
                phone="+919876543200",
                verification_status=True,
            )
            db.add(org_alpha)
            db.flush()
            print(f"Created Org Alpha: {org_alpha.name} (ID: {org_alpha.id})")
        elif reconcile_existing:
            org_alpha.organization_type = OrganizationType.NGO
            org_alpha.address = "Marine Drive, Ernakulam, Kerala 682031"
            org_alpha.email = "contact@alpha.staging.pawsos.org"
            org_alpha.phone = "+919876543200"
            org_alpha.verification_status = True

        org_beta = (
            db.query(Organization)
            .filter(Organization.name == "Organization Beta - Animal Aid Alliance")
            .first()
        )
        if not org_beta:
            org_beta = Organization(
                name="Organization Beta - Animal Aid Alliance",
                organization_type=OrganizationType.NGO,
                address="Infopark Expressway, Kakkanad, Kerala 682042",
                email="contact@beta.staging.pawsos.org",
                phone="+919876543299",
                verification_status=True,
            )
            db.add(org_beta)
            db.flush()
            print(f"Created Org Beta: {org_beta.name} (ID: {org_beta.id})")
        elif reconcile_existing:
            org_beta.organization_type = OrganizationType.NGO
            org_beta.address = "Infopark Expressway, Kakkanad, Kerala 682042"
            org_beta.email = "contact@beta.staging.pawsos.org"
            org_beta.phone = "+919876543299"
            org_beta.verification_status = True

        vet_facility_alpha = (
            db.query(VeterinaryFacility)
            .filter(VeterinaryFacility.name == "Cochin PetCare Emergency Hospital")
            .first()
        )
        if not vet_facility_alpha:
            vet_facility_alpha = VeterinaryFacility(
                organization_id=org_alpha.id,
                name="Cochin PetCare Emergency Hospital",
                phone="+919876543201",
                email="hospital.alpha@staging.pawsos.org",
                latitude=9.9816,
                longitude=76.2999,
                address="MG Road, Ernakulam, Kerala 682016",
                supports_emergency=True,
                is_24_hours=True,
                is_verified=True,
            )
            db.add(vet_facility_alpha)
            db.flush()
            print(
                f"Created Vet Facility Alpha: {vet_facility_alpha.name} "
                f"(ID: {vet_facility_alpha.id})"
            )
        elif reconcile_existing:
            vet_facility_alpha.organization_id = org_alpha.id
            vet_facility_alpha.phone = "+919876543201"
            vet_facility_alpha.email = "hospital.alpha@staging.pawsos.org"
            vet_facility_alpha.latitude = 9.9816
            vet_facility_alpha.longitude = 76.2999
            vet_facility_alpha.address = "MG Road, Ernakulam, Kerala 682016"
            vet_facility_alpha.supports_emergency = True
            vet_facility_alpha.is_24_hours = True
            vet_facility_alpha.is_verified = True

        vet_facility_beta = (
            db.query(VeterinaryFacility)
            .filter(VeterinaryFacility.name == "Alliance Trauma & Critical Care Clinic")
            .first()
        )
        if not vet_facility_beta:
            vet_facility_beta = VeterinaryFacility(
                organization_id=org_beta.id,
                name="Alliance Trauma & Critical Care Clinic",
                phone="+919876543291",
                email="hospital.beta@staging.pawsos.org",
                latitude=10.0150,
                longitude=76.3400,
                address="Civil Station Road, Kakkanad, Kerala 682030",
                supports_emergency=True,
                is_24_hours=True,
                is_verified=True,
            )
            db.add(vet_facility_beta)
            db.flush()
            print(
                f"Created Vet Facility Beta: {vet_facility_beta.name} "
                f"(ID: {vet_facility_beta.id})"
            )
        elif reconcile_existing:
            vet_facility_beta.organization_id = org_beta.id
            vet_facility_beta.phone = "+919876543291"
            vet_facility_beta.email = "hospital.beta@staging.pawsos.org"
            vet_facility_beta.latitude = 10.0150
            vet_facility_beta.longitude = 76.3400
            vet_facility_beta.address = "Civil Station Road, Kakkanad, Kerala 682030"
            vet_facility_beta.supports_emergency = True
            vet_facility_beta.is_24_hours = True
            vet_facility_beta.is_verified = True

        accounts = [
            {
                "email": "citizen@staging.pawsos.org",
                "phone": "+919876543210",
                "name": "Citizen Pilot User",
                "role": UserRole.CITIZEN,
                "org_id": None,
                "facility_id": None,
            },
            {
                "email": "superadmin@staging.pawsos.org",
                "phone": "+919876543215",
                "name": "System Administrator",
                "role": UserRole.SUPER_ADMIN,
                "org_id": None,
                "facility_id": None,
            },
            {
                "email": "admin@staging.pawsos.org",
                "phone": "+919876543214",
                "name": "Priya Sharma (Admin Alpha)",
                "role": UserRole.NGO_ADMIN,
                "org_id": org_alpha.id,
                "facility_id": None,
            },
            {
                "email": "admin.a@staging.pawsos.org",
                "phone": "+919876543216",
                "name": "Anil Kumar (Admin Alpha 2)",
                "role": UserRole.NGO_ADMIN,
                "org_id": org_alpha.id,
                "facility_id": None,
            },
            {
                "email": "rescuer.a@staging.pawsos.org",
                "phone": "+919876543211",
                "name": "Arjun Nair (Responder Alpha 1)",
                "role": UserRole.RESCUER,
                "org_id": org_alpha.id,
                "facility_id": None,
                "lat": 9.9850,
                "lng": 76.2980,
            },
            {
                "email": "rescuer.b@staging.pawsos.org",
                "phone": "+919876543212",
                "name": "Sneha Menon (Responder Alpha 2)",
                "role": UserRole.RESCUER,
                "org_id": org_alpha.id,
                "facility_id": None,
                "lat": 9.9910,
                "lng": 76.3020,
            },
            {
                "email": "vet@staging.pawsos.org",
                "phone": "+919876543213",
                "name": "Dr. Rajesh Varma (Vet Alpha)",
                "role": UserRole.VETERINARIAN,
                "org_id": org_alpha.id,
                "facility_id": vet_facility_alpha.id,
            },
            {
                "email": "admin.b@staging.pawsos.org",
                "phone": "+919876543294",
                "name": "Kavita Iyer (Admin Beta)",
                "role": UserRole.NGO_ADMIN,
                "org_id": org_beta.id,
                "facility_id": None,
            },
            {
                "email": "rescuer.b1@staging.pawsos.org",
                "phone": "+919876543295",
                "name": "Rohan Das (Responder Beta 1)",
                "role": UserRole.RESCUER,
                "org_id": org_beta.id,
                "facility_id": None,
                "lat": 10.0120,
                "lng": 76.3420,
            },
            {
                "email": "rescuer.b2@staging.pawsos.org",
                "phone": "+919876543296",
                "name": "Maya Sen (Responder Beta 2)",
                "role": UserRole.RESCUER,
                "org_id": org_beta.id,
                "facility_id": None,
                "lat": 10.0180,
                "lng": 76.3380,
            },
            {
                "email": "vet.b@staging.pawsos.org",
                "phone": "+919876543297",
                "name": "Dr. Ananya Roy (Vet Beta)",
                "role": UserRole.VETERINARIAN,
                "org_id": org_beta.id,
                "facility_id": vet_facility_beta.id,
            },
        ]

        # Preflight the full reserved identity set before mutating any user.
        for acc in accounts:
            by_email = db.query(User).filter(User.email == acc["email"]).first()
            by_phone = db.query(User).filter(User.phone == acc["phone"]).first()
            validate_staging_identity_collision(
                expected_email=acc["email"],
                expected_phone=acc["phone"],
                existing_by_email=by_email,
                existing_by_phone=by_phone,
            )

        target_users = []
        for acc in accounts:
            existing = db.query(User).filter(User.email == acc["email"]).first()

            if existing is None:
                user = User(
                    full_name=acc["name"],
                    email=acc["email"],
                    phone=acc["phone"],
                    password_hash=get_password_hash(staging_pwd),
                    role=acc["role"],
                    organization_id=acc["org_id"],
                    veterinary_facility_id=acc["facility_id"],
                    is_active=True,
                    is_verified=True,
                )
                db.add(user)
                db.flush()
                print(f"Created user: {acc['name']} ({acc['role'].value})")
            else:
                user = existing
                if reconcile_existing:
                    user.full_name = acc["name"]
                    user.phone = acc["phone"]
                    user.password_hash = get_password_hash(staging_pwd)
                    user.role = acc["role"]
                    user.organization_id = acc["org_id"]
                    user.veterinary_facility_id = acc["facility_id"]
                    user.is_active = True
                    user.is_verified = True
                    print(f"Reconciled user: {acc['email']} ({acc['role'].value})")

            target_users.append(user)

            if acc["role"] == UserRole.RESCUER:
                profile = (
                    db.query(RescuerProfile)
                    .filter(RescuerProfile.user_id == user.id)
                    .first()
                )
                if profile is None:
                    profile = RescuerProfile(
                        user_id=user.id,
                        organization_id=acc["org_id"],
                        availability_status=RescuerAvailability.AVAILABLE,
                        latitude=acc.get("lat", 9.9850),
                        longitude=acc.get("lng", 76.2980),
                        vehicle_available=True,
                        experience_level="Advanced",
                        reliability_score=98.0,
                        last_location_update=datetime.now(timezone.utc),
                    )
                    db.add(profile)
                    print(f"  Created rescuer profile for {acc['name']}")
                elif reconcile_existing:
                    profile.organization_id = acc["org_id"]
                    profile.availability_status = RescuerAvailability.AVAILABLE
                    profile.latitude = acc.get("lat", 9.9850)
                    profile.longitude = acc.get("lng", 76.2980)
                    profile.vehicle_available = True
                    profile.experience_level = "Advanced"
                    profile.reliability_score = 98.0
                    profile.last_location_update = datetime.now(timezone.utc)
                    print(f"  Reconciled rescuer profile for {acc['email']}")

        revoked = 0
        if reconcile_existing:
            db.flush()
            user_ids = [user.id for user in target_users]
            revoked = (
                db.query(RefreshSession)
                .filter(
                    RefreshSession.user_id.in_(user_ids),
                    RefreshSession.revoked_at.is_(None),
                )
                .update(
                    {"revoked_at": datetime.now(timezone.utc)},
                    synchronize_session=False,
                )
            )

        db.commit()

        if reconcile_existing:
            print(
                "Staging reconciliation completed successfully: "
                f"canonical_users={len(target_users)}, "
                f"active_refresh_sessions_revoked={revoked}."
            )
        else:
            print("Multi-tenant staging seed completed successfully with secure credentials!")
    except Exception as exc:
        db.rollback()
        print(f"Error seeding database: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_staging_database()
