"""Staging Seed Data Script for PawReach MVP Phase 2.5 Pilot Testing.
Creates initial test organization, partner veterinary facility, and designated test accounts.
"""
import sys
import os
import uuid
from datetime import datetime

# Add parent directory to sys.path so app modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal, engine, Base
from app.models.organization import Organization
from app.models.veterinary_facility import VeterinaryFacility
from app.models.user import User
from app.models.rescuer_profile import RescuerProfile
from app.core.security import get_password_hash
from app.core.constants import UserRole, RescuerAvailability, OrganizationType

def seed_staging_database():
    print("Seeding PawReach staging database...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Create Staging NGO Organization
        ngo = db.query(Organization).filter(Organization.name == "Cochin Animal Rescue Network").first()
        if not ngo:
            ngo = Organization(
                name="Cochin Animal Rescue Network",
                organization_type=OrganizationType.NGO,
                address="Marine Drive, Ernakulam, Kerala 682031",
                email="contact@staging.pawsos.org",
                phone="+919876543200",
                verification_status=True,
            )
            db.add(ngo)
            db.flush()
            print(f"Created NGO Organization: {ngo.name} ({ngo.id})")

        # 2. Create Partner Veterinary Facility
        vet_facility = db.query(VeterinaryFacility).filter(VeterinaryFacility.name == "Cochin PetCare Emergency Hospital").first()
        if not vet_facility:
            vet_facility = VeterinaryFacility(
                organization_id=ngo.id,
                name="Cochin PetCare Emergency Hospital",
                phone="+919876543201",
                email="hospital@staging.pawsos.org",
                latitude=9.9816,
                longitude=76.2999,
                address="MG Road, Ernakulam, Kerala 682016",
                supports_emergency=True,
                is_24_hours=True,
                is_verified=True,
            )
            db.add(vet_facility)
            db.flush()
            print(f"Created Veterinary Facility: {vet_facility.name} ({vet_facility.id})")

        default_pwd = get_password_hash("StagingPass123!")

        # 3. Create Designated Staging Accounts
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
                "email": "rescuer.a@staging.pawsos.org",
                "phone": "+919876543211",
                "name": "Arjun Nair (Rescuer A)",
                "role": UserRole.RESCUER,
                "org_id": ngo.id,
                "facility_id": None,
                "lat": 9.9850,
                "lng": 76.2980,
            },
            {
                "email": "rescuer.b@staging.pawsos.org",
                "phone": "+919876543212",
                "name": "Sneha Menon (Rescuer B)",
                "role": UserRole.RESCUER,
                "org_id": ngo.id,
                "facility_id": None,
                "lat": 9.9910,
                "lng": 76.3020,
            },
            {
                "email": "vet@staging.pawsos.org",
                "phone": "+919876543213",
                "name": "Dr. Rajesh Varma",
                "role": UserRole.VETERINARIAN,
                "org_id": ngo.id,
                "facility_id": vet_facility.id,
            },
            {
                "email": "admin@staging.pawsos.org",
                "phone": "+919876543214",
                "name": "Priya Sharma (NGO Admin)",
                "role": UserRole.NGO_ADMIN,
                "org_id": ngo.id,
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
        ]

        for acc in accounts:
            existing = db.query(User).filter(User.email == acc["email"]).first()
            if not existing:
                u = User(
                    full_name=acc["name"],
                    email=acc["email"],
                    phone=acc["phone"],
                    password_hash=default_pwd,
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
                        last_location_update=datetime.utcnow(),
                    )
                    db.add(profile)
                    print(f"  Created rescuer profile for {acc['name']}")

        db.commit()
        print("Staging seed completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_staging_database()
