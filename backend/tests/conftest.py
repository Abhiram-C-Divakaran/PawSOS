import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import uuid
from datetime import datetime

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.rescuer_profile import RescuerProfile
from app.models.organization import Organization
from app.models.veterinary_facility import VeterinaryFacility
from app.core.security import get_password_hash, create_access_token, create_refresh_token
from app.core.constants import UserRole, RescuerAvailability, OrganizationType

# Create in-memory SQLite engine for tests
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def citizen_user(db):
    user = User(
        full_name="Test Citizen",
        email=f"citizen_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.CITIZEN,
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def citizen_token(citizen_user):
    return create_access_token(citizen_user.id)

@pytest.fixture
def rescuer_user(db):
    user = User(
        full_name="Test Rescuer",
        email=f"rescuer_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9197{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.RESCUER,
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = RescuerProfile(
        user_id=user.id,
        availability_status=RescuerAvailability.AVAILABLE,
        latitude=19.0760,
        longitude=72.8777,
        current_location="POINT(72.8777 19.0760)",
        last_location_update=datetime.utcnow()
    )
    db.add(profile)
    db.commit()

    return user

@pytest.fixture
def rescuer_token(rescuer_user):
    return create_access_token(rescuer_user.id)

@pytest.fixture
def vet_user(db, test_facility):
    user = User(
        full_name="Test Vet",
        email=f"vet_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9196{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.VETERINARIAN,
        veterinary_facility_id=test_facility.id,
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def vet_token(vet_user):
    return create_access_token(vet_user.id)

@pytest.fixture
def admin_user(db):
    user = User(
        full_name="Test Admin",
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        phone=f"+9195{uuid.uuid4().hex[:8]}",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def admin_token(admin_user):
    return create_access_token(admin_user.id)

@pytest.fixture
def test_facility(db):
    fac = VeterinaryFacility(
        name="Test Emergency Animal Clinic",
        phone="+912226001111",
        email="clinic@test.com",
        latitude=19.0600,
        longitude=72.8300,
        location="POINT(72.8300 19.0600)",
        address="Bandra West, Mumbai",
        supports_emergency=True,
        is_24_hours=True,
        is_verified=True
    )
    db.add(fac)
    db.commit()
    db.refresh(fac)
    return fac
