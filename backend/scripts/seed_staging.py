"""Staging Seed Data Script for PawReach Pilot Testing.
Creates two distinct staging NGO organizations (Org Alpha & Org Beta), partner veterinary facilities,
and designated test accounts for cross-tenant pilot validation.
Requires STAGING_SEED_PASSWORD environment variable.
"""
import sys
import os
import uuid
import re
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

def seed_staging_database():
    env = (os.environ.get("ENVIRONMENT") or settings.ENVIRONMENT or "").lower()
    if env == "production":
        raise RuntimeError(
            "FATAL: Staging seeding is strictly prohibited in production environments (ENVIRONMENT=production)."
        )

    # 1. Enforce STAGING_SEED_PASSWORD validation
    staging_pwd = validate_staging_password(os.environ.get("STAGING_SEED_PASSWORD"))

    # 2. Verify schema exists without creating or mutating outside Alembic
    inspector = inspect(engine)
    required_tables = ["organizations", "veterinary_facilities", "users", "rescuer_profiles"]
    missing = [tbl for tbl in required_tables if not inspector.has_table(tbl)]
    if missing:
        raise RuntimeError(
            f"Database schema not initialized. Missing tables: {missing}. "
            "The staging seed script does not create or mutate schema. "
            "Please run 'alembic upgrade head' before running seed_staging.py."
        )

    print("Seeding PawReach staging database with validated multi-tenant credentials...")
    db = SessionLocal()

    try:
        # 1. Organization Alpha (Primary NGO)
        org_alpha = db.query(Organization).filter(Organization.name == "Organization Alpha - Stray Relief").first()
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

        # 2. Organization Beta (Isolated Second NGO)
        org_beta = db.query(Organization).filter(Organization.name == "Organization Beta - Animal Aid Alliance").first()
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

        # 3. Veterinary Facility Alpha (Linked to Org Alpha)
        vet_facility_alpha = db.query(VeterinaryFacility).filter(VeterinaryFacility.name == "Cochin PetCare Emergency Hospital").first()
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
            print(f"Created Vet Facility Alpha: {vet_facility_alpha.name} (ID: {vet_facility_alpha.id})")

        # 4. Veterinary Facility Beta (Linked to Org Beta)
        vet_facility_beta = db.query(VeterinaryFacility).filter(VeterinaryFacility.name == "Alliance Trauma & Critical Care Clinic").first()
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
            print(f"Created Vet Facility Beta: {vet_facility_beta.name} (ID: {vet_facility_beta.id})")

        hashed_pwd = get_password_hash(staging_pwd)

        # 5. Designated Staging Accounts (Multi-Tenant)
        accounts = [
            # Global Roles
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
            # Organization Alpha Team
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
            # Organization Beta Team (Tenant Boundary Testing)
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

        for acc in accounts:
            existing = db.query(User).filter(User.email == acc["email"]).first()
            if not existing:
                u = User(
                    full_name=acc["name"],
                    email=acc["email"],
                    phone=acc["phone"],
                    password_hash=hashed_pwd,
                    role=acc["role"],
                    organization_id=acc["org_id"],
                    veterinary_facility_id=acc["facility_id"],
                    is_active=True,
                    is_verified=True,
                )
                db.add(u)
                db.flush()
                print(f"Created user: {acc['name']} ({acc['role'].value})")

                if acc["role"] == UserRole.RESCUER:
                    profile = RescuerProfile(
                        user_id=u.id,
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

        db.commit()
        print("Multi-tenant staging seed completed successfully with secure credentials!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_staging_database()
