"""Deterministic E2E Test Data Seed Script for PawReach Phase 2.8 Fullstack Validation.

Seeds fixed organizations, veterinary facilities, deterministic test accounts,
and pre-staged scenarios for unmocked Playwright fullstack testing.
"""
import sys
import os
import uuid
from datetime import datetime, timedelta

# Add parent directory to sys.path so app modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal, engine, Base
from app.models.organization import Organization
from app.models.veterinary_facility import VeterinaryFacility
from app.models.user import User
from app.models.rescuer_profile import RescuerProfile
from app.models.rescue_case import RescueCase
from app.models.rescue_assignment import RescueAssignment
from app.core.security import get_password_hash
from app.core.constants import (
    UserRole,
    RescuerAvailability,
    OrganizationType,
    RescueStatus,
    RescuePriority,
    AssignmentStatus,
)

E2E_PASSWORD = "E2ETestPassword123!"

def seed_e2e():
    print("Seeding PawReach E2E fullstack test database...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Clean existing E2E seed data to guarantee deterministic freshness
        e2e_emails = [
            "citizen.e2e@pawreach.test",
            "rescuer1.e2e@pawreach.test",
            "rescuer2.e2e@pawreach.test",
            "vet.e2e@pawreach.test",
            "ngoadminA.e2e@pawreach.test",
            "ngoadminB.e2e@pawreach.test",
            "superadmin.e2e@pawreach.test",
        ]
        existing_users = db.query(User).filter(User.email.in_(e2e_emails)).all()
        user_ids = [u.id for u in existing_users]
        if user_ids:
            # Clean dependent assignments and profiles
            db.query(RescueAssignment).filter(RescueAssignment.rescuer_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(RescueCase).filter(RescueCase.reporter_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(RescuerProfile).filter(RescuerProfile.user_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
            db.commit()

        # 2. Organizations
        org_a = db.query(Organization).filter(Organization.name == "PawReach Rescue Alpha").first()
        if not org_a:
            org_a = Organization(
                name="PawReach Rescue Alpha",
                organization_type=OrganizationType.NGO,
                address="Colaba, Mumbai, Maharashtra 400005",
                email="orga@pawreach.test",
                phone="+919811111111",
                operating_region="South Mumbai",
                verification_status=True,
            )
            db.add(org_a)
            db.flush()

        org_b = db.query(Organization).filter(Organization.name == "PawReach Rescue Beta").first()
        if not org_b:
            org_b = Organization(
                name="PawReach Rescue Beta",
                organization_type=OrganizationType.NGO,
                address="Andheri, Mumbai, Maharashtra 400053",
                email="orgb@pawreach.test",
                phone="+919822222222",
                operating_region="North Mumbai",
                verification_status=True,
            )
            db.add(org_b)
            db.flush()

        # 3. Veterinary Facility for Org A
        vet_facility = db.query(VeterinaryFacility).filter(VeterinaryFacility.name == "South Mumbai Animal Hospital").first()
        if not vet_facility:
            vet_facility = VeterinaryFacility(
                organization_id=org_a.id,
                name="South Mumbai Animal Hospital",
                phone="+919833333333",
                email="vetfacilitya@pawreach.test",
                latitude=18.9215,
                longitude=72.8335,
                address="Colaba Causeway, Mumbai 400005",
                supports_emergency=True,
                is_24_hours=True,
                is_verified=True,
            )
            db.add(vet_facility)
            db.flush()

        # 4. Create Deterministic Accounts
        pwd_hash = get_password_hash(E2E_PASSWORD)

        # 4.1 Citizen
        citizen = User(
            email="citizen.e2e@pawreach.test",
            phone="+919800000001",
            full_name="E2E Citizen Reporter",
            password_hash=pwd_hash,
            role=UserRole.CITIZEN,
            is_active=True,
            is_verified=True,
        )
        db.add(citizen)

        # 4.2 Rescuer 1 (Org A, Colaba location)
        rescuer1 = User(
            email="rescuer1.e2e@pawreach.test",
            phone="+919800000002",
            full_name="E2E Rescuer One",
            password_hash=pwd_hash,
            role=UserRole.RESCUER,
            organization_id=org_a.id,
            is_active=True,
            is_verified=True,
        )
        db.add(rescuer1)

        # 4.3 Rescuer 2 (Org A, near Colaba location)
        rescuer2 = User(
            email="rescuer2.e2e@pawreach.test",
            phone="+919800000003",
            full_name="E2E Rescuer Two",
            password_hash=pwd_hash,
            role=UserRole.RESCUER,
            organization_id=org_a.id,
            is_active=True,
            is_verified=True,
        )
        db.add(rescuer2)

        # 4.4 Vet (South Mumbai Hospital)
        vet = User(
            email="vet.e2e@pawreach.test",
            phone="+919800000004",
            full_name="Dr. E2E Veterinarian",
            password_hash=pwd_hash,
            role=UserRole.VETERINARIAN,
            organization_id=org_a.id,
            veterinary_facility_id=vet_facility.id,
            is_active=True,
            is_verified=True,
        )
        db.add(vet)

        # 4.5 NGO Admin Org A
        ngo_admin_a = User(
            email="ngoadminA.e2e@pawreach.test",
            phone="+919800000005",
            full_name="E2E Admin Org A",
            password_hash=pwd_hash,
            role=UserRole.NGO_ADMIN,
            organization_id=org_a.id,
            is_active=True,
            is_verified=True,
        )
        db.add(ngo_admin_a)

        # 4.6 NGO Admin Org B
        ngo_admin_b = User(
            email="ngoadminB.e2e@pawreach.test",
            phone="+919800000006",
            full_name="E2E Admin Org B",
            password_hash=pwd_hash,
            role=UserRole.NGO_ADMIN,
            organization_id=org_b.id,
            is_active=True,
            is_verified=True,
        )
        db.add(ngo_admin_b)

        # 4.7 Super Admin
        super_admin = User(
            email="superadmin.e2e@pawreach.test",
            phone="+919800000007",
            full_name="E2E Super Admin",
            password_hash=pwd_hash,
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
        )
        db.add(super_admin)
        db.flush()

        # 5. Create Rescuer Profiles
        profile1 = RescuerProfile(
            user_id=rescuer1.id,
            organization_id=org_a.id,
            availability_status=RescuerAvailability.AVAILABLE,
            latitude=18.9220,
            longitude=72.8340,
            service_radius_km=15.0,
            vehicle_available=True,
            experience_level="Expert",
            last_location_update=datetime.utcnow(),
            reliability_score=98.5,
        )
        db.add(profile1)

        profile2 = RescuerProfile(
            user_id=rescuer2.id,
            organization_id=org_a.id,
            availability_status=RescuerAvailability.AVAILABLE,
            latitude=18.9250,
            longitude=72.8370,
            service_radius_km=15.0,
            vehicle_available=True,
            experience_level="Intermediate",
            last_location_update=datetime.utcnow(),
            reliability_score=95.0,
        )
        db.add(profile2)

        # 6. Pre-staged Rescue Cases for Scenarios
        # Scenario Case: Org B incident (for Cross-Tenant check: Org A Admin must NOT be able to access or assign)
        db.query(RescueCase).filter(RescueCase.case_number.in_(["E2E-CASE-ORGB-001", "E2E-CASE-CONCURRENT-001", "E2E-CASE-VET-001"])).delete(synchronize_session=False)

        case_org_b = RescueCase(
            case_number="E2E-CASE-ORGB-001",
            reporter_id=citizen.id,
            organization_id=org_b.id,
            species="Canine",
            description="Org B Confidential Animal Case in Andheri",
            latitude=19.1197,
            longitude=72.8464,
            address_text="Andheri Station West, Mumbai",
            status=RescueStatus.REPORTED,
            triage_priority=RescuePriority.URGENT,
            triage_score=70,
            created_at=datetime.utcnow() - timedelta(minutes=30),
        )
        db.add(case_org_b)

        # Scenario Case: Concurrent Acceptance Case (with offers sent to both rescuer1 and rescuer2)
        case_concurrent = RescueCase(
            case_number="E2E-CASE-CONCURRENT-001",
            reporter_id=citizen.id,
            organization_id=org_a.id,
            species="Canine",
            description="Emergency dog needing immediate assistance at Gateway of India",
            latitude=18.9220,
            longitude=72.8347,
            address_text="Gateway of India, Colaba, Mumbai",
            status=RescueStatus.SEARCHING_RESPONDER,
            triage_priority=RescuePriority.CRITICAL,
            triage_score=95,
            created_at=datetime.utcnow() - timedelta(minutes=5),
        )
        db.add(case_concurrent)
        db.flush()

        offer1 = RescueAssignment(
            rescue_case_id=case_concurrent.id,
            rescuer_id=rescuer1.id,
            assignment_status=AssignmentStatus.PENDING,
            offered_at=datetime.utcnow(),
            dispatch_score=95.0,
            distance_km=0.5,
        )
        offer2 = RescueAssignment(
            rescue_case_id=case_concurrent.id,
            rescuer_id=rescuer2.id,
            assignment_status=AssignmentStatus.PENDING,
            offered_at=datetime.utcnow(),
            dispatch_score=90.0,
            distance_km=1.1,
        )
        db.add_all([offer1, offer2])

        # Scenario Case: Animal at facility ready for veterinary intake
        case_vet = RescueCase(
            case_number="E2E-CASE-VET-001",
            reporter_id=citizen.id,
            organization_id=org_a.id,
            species="Feline",
            description="Injured cat transported to hospital",
            latitude=18.9215,
            longitude=72.8335,
            address_text="Colaba Animal Hospital Intake",
            status=RescueStatus.AT_VETERINARY_FACILITY,
            triage_priority=RescuePriority.URGENT,
            triage_score=75,
            veterinary_facility_id=vet_facility.id,
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
        db.add(case_vet)

        db.commit()
        print("E2E seed completed successfully:")
        print(f"  Org A: {org_a.name} ({org_a.id})")
        print(f"  Org B: {org_b.name} ({org_b.id})")
        print(f"  Vet Facility: {vet_facility.name} ({vet_facility.id})")
        print(f"  Users seeded: {len(e2e_emails)} accounts (Password: {E2E_PASSWORD})")
        print("  Pre-staged cases: E2E-CASE-ORGB-001, E2E-CASE-CONCURRENT-001, E2E-CASE-VET-001")

    except Exception as e:
        db.rollback()
        print(f"Error seeding E2E database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_e2e()
