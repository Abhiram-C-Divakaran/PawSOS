import uuid
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import Base
from app.models.user import User
from app.models.organization import Organization
from app.models.rescue_case import RescueCase
from app.core.security import get_password_hash
from app.core.constants import UserRole, OrganizationType, RescueStatus, RescuePriority

def seed_db():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    db: Session = SessionLocal()
    
    try:
        # Check if already seeded
        if db.query(User).first():
            print("Database already seeded.")
            return

        print("Seeding Users...")
        # 1. Citizen
        citizen = User(
            full_name="John Citizen",
            email="citizen@example.com",
            phone="+1234567890",
            password_hash=get_password_hash("password123"),
            role=UserRole.CITIZEN,
            is_active=True,
            is_verified=True
        )
        
        # 2. Rescuer 1
        rescuer1 = User(
            full_name="Alice Rescuer",
            email="alice@example.com",
            phone="+1234567891",
            password_hash=get_password_hash("password123"),
            role=UserRole.RESCUER,
            is_active=True,
            is_verified=True
        )
        
        # 3. Rescuer 2
        rescuer2 = User(
            full_name="Bob Rescuer",
            email="bob@example.com",
            phone="+1234567892",
            password_hash=get_password_hash("password123"),
            role=UserRole.RESCUER,
            is_active=True,
            is_verified=True
        )

        # 4. Veterinarian
        vet = User(
            full_name="Dr. Sarah Vet",
            email="sarah@example.com",
            phone="+1234567893",
            password_hash=get_password_hash("password123"),
            role=UserRole.VETERINARIAN,
            is_active=True,
            is_verified=True
        )

        # 5. Admin
        admin = User(
            full_name="Admin User",
            email="admin@example.com",
            phone="+1234567894",
            password_hash=get_password_hash("password123"),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True
        )
        
        db.add_all([citizen, rescuer1, rescuer2, vet, admin])
        db.commit()

        print("Seeding Organizations...")
        org = Organization(
            name="City Animal Rescue NGO",
            organization_type=OrganizationType.NGO,
            email="contact@cityrescue.org",
            phone="+1987654321",
            latitude=19.0760,
            longitude=72.8777,
            verification_status=True
        )
        db.add(org)
        db.commit()
        db.refresh(org)

        rescuer1.organization_id = org.id
        db.commit()

        print("Seeding Rescue Case...")
        case = RescueCase(
            case_number="PR-DEMO01",
            reporter_id=citizen.id,
            species="Dog",
            description="Injured dog, unable to walk, bleeding",
            latitude=19.0750,
            longitude=72.8780,
            address_text="Linking Road, Bandra West, Mumbai",
            bleeding=True,
            can_walk=False,
            conscious=True,
            vehicle_accident=True,
            triage_score=100,
            triage_priority=RescuePriority.CRITICAL,
            triage_reason="Vehicle collision reported, Visible bleeding reported",
            status=RescueStatus.TRIAGED
        )
        db.add(case)
        db.commit()
        
        print("Seed complete.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
