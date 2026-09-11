import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.user import User
from app.models.rescuer_profile import RescuerProfile
from app.models.organization import Organization
from app.models.veterinary_facility import VeterinaryFacility
from app.models.rescue_case import RescueCase
from app.models.animal_image import AnimalImage
from app.models.rescue_status_history import RescueStatusHistory
from app.core.security import get_password_hash
from app.core.constants import (
    UserRole,
    OrganizationType,
    RescueStatus,
    RescuePriority,
    RescuerAvailability
)

def seed_db():
    db: Session = SessionLocal()
    
    try:
        # Check if already seeded
        if db.query(User).first():
            print("Database already contains data. Skipping seed.")
            return

        print("Seeding Users...")
        # 1. Citizen
        citizen = User(
            full_name="John Citizen",
            email="citizen@example.com",
            phone="+919876543210",
            password_hash=get_password_hash("password123"),
            role=UserRole.CITIZEN,
            is_active=True,
            is_verified=True
        )
        
        # 2. Rescuer 1 (Alice)
        rescuer1 = User(
            full_name="Alice Rescuer",
            email="alice@example.com",
            phone="+919876543211",
            password_hash=get_password_hash("password123"),
            role=UserRole.RESCUER,
            is_active=True,
            is_verified=True
        )
        
        # 3. Rescuer 2 (Bob)
        rescuer2 = User(
            full_name="Bob Rescuer",
            email="bob@example.com",
            phone="+919876543212",
            password_hash=get_password_hash("password123"),
            role=UserRole.RESCUER,
            is_active=True,
            is_verified=True
        )

        # 4. Veterinarian
        vet = User(
            full_name="Dr. Sarah Vet",
            email="sarah@example.com",
            phone="+919876543213",
            password_hash=get_password_hash("password123"),
            role=UserRole.VETERINARIAN,
            is_active=True,
            is_verified=True
        )

        # 5. Super Admin
        admin = User(
            full_name="Admin User",
            email="admin@example.com",
            phone="+919876543214",
            password_hash=get_password_hash("password123"),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True
        )
        
        db.add_all([citizen, rescuer1, rescuer2, vet, admin])
        db.commit()

        print("Seeding Organization & Veterinary Facility...")
        org = Organization(
            name="Mumbai Animal Rescue NGO",
            organization_type=OrganizationType.NGO,
            email="contact@mumbairescue.org",
            phone="+912226401234",
            latitude=19.0760,
            longitude=72.8777,
            verification_status=True
        )
        db.add(org)
        db.commit()
        db.refresh(org)

        rescuer1.organization_id = org.id
        rescuer2.organization_id = org.id
        db.commit()

        # Rescuer Profiles
        p1 = RescuerProfile(
            user_id=rescuer1.id,
            availability_status=RescuerAvailability.AVAILABLE,
            latitude=19.0760,
            longitude=72.8777,
            current_location="POINT(72.8777 19.0760)",
            vehicle_available=True,
            experience_level="Advanced",
            service_radius_km=15.0,
            last_location_update=datetime.utcnow(),
            organization_id=org.id
        )
        p2 = RescuerProfile(
            user_id=rescuer2.id,
            availability_status=RescuerAvailability.AVAILABLE,
            latitude=19.0800,
            longitude=72.8850,
            current_location="POINT(72.8850 19.0800)",
            vehicle_available=True,
            experience_level="Intermediate",
            service_radius_km=10.0,
            last_location_update=datetime.utcnow(),
            organization_id=org.id
        )
        db.add_all([p1, p2])
        db.commit()

        # Veterinary Facility
        facility = VeterinaryFacility(
            organization_id=org.id,
            name="Bandra Pet Care Emergency Hospital",
            phone="+912226456789",
            email="care@bandrapetcare.com",
            latitude=19.0596,
            longitude=72.8295,
            location="POINT(72.8295 19.0596)",
            address="Hill Road, Bandra West, Mumbai",
            supports_emergency=True,
            is_24_hours=True,
            is_verified=True
        )
        db.add(facility)
        db.commit()
        db.refresh(facility)

        print("Seeding Initial Rescue Cases...")
        # Case 1: Open rescue near Alice
        case1 = RescueCase(
            case_number="PR-MUM001",
            reporter_id=citizen.id,
            species="Dog",
            description="Injured stray dog near Bandra station, unable to walk, bleeding from leg.",
            latitude=19.0550,
            longitude=72.8400,
            location="POINT(72.8400 19.0550)",
            address_text="Near Station Road, Bandra West, Mumbai",
            bleeding=True,
            can_walk=False,
            conscious=True,
            vehicle_accident=True,
            breathing_difficulty=False,
            triage_score=100,
            triage_priority=RescuePriority.CRITICAL,
            triage_reason="Vehicle collision reported, Visible bleeding reported, Animal unable to walk",
            status=RescueStatus.TRIAGED
        )
        db.add(case1)
        db.commit()
        db.refresh(case1)

        img1 = AnimalImage(
            rescue_case_id=case1.id,
            image_url="/uploads/demo_dog.jpg",
            image_type="REPORT",
            uploaded_by=citizen.id
        )
        hist1 = RescueStatusHistory(
            rescue_case_id=case1.id,
            previous_status=RescueStatus.REPORTED,
            new_status=RescueStatus.TRIAGED,
            changed_by=citizen.id,
            notes="Auto-triaged based on reported emergency condition"
        )
        db.add_all([img1, hist1])

        # Case 2: Case already at veterinary facility awaiting Dr. Sarah
        case2 = RescueCase(
            case_number="PR-MUM002",
            reporter_id=citizen.id,
            species="Cat",
            description="Kitten rescued from drain with hypothermia and leg fracture.",
            latitude=19.0600,
            longitude=72.8350,
            location="POINT(72.8350 19.0600)",
            address_text="Pali Hill, Bandra West, Mumbai",
            bleeding=False,
            can_walk=False,
            conscious=True,
            vehicle_accident=False,
            breathing_difficulty=True,
            triage_score=80,
            triage_priority=RescuePriority.URGENT,
            triage_reason="Severe breathing difficulty, Animal unable to walk",
            status=RescueStatus.AT_VETERINARY_FACILITY,
            veterinary_facility_id=facility.id
        )
        db.add(case2)
        db.commit()
        db.refresh(case2)

        img2 = AnimalImage(
            rescue_case_id=case2.id,
            image_url="/uploads/demo_cat.jpg",
            image_type="REPORT",
            uploaded_by=citizen.id
        )
        hist2 = RescueStatusHistory(
            rescue_case_id=case2.id,
            previous_status=RescueStatus.TRANSPORTING,
            new_status=RescueStatus.AT_VETERINARY_FACILITY,
            changed_by=rescuer1.id,
            notes="Admitted at Bandra Pet Care Emergency Hospital"
        )
        db.add_all([img2, hist2])

        db.commit()
        print("Database seeding completed successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
