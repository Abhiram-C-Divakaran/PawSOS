import io
import pytest
from PIL import Image
from datetime import datetime

from app.models.user import User
from app.models.rescuer_profile import RescuerProfile
from app.models.organization import Organization
from app.models.veterinary_facility import VeterinaryFacility
from app.core.constants import UserRole, OrganizationType, RescuerAvailability
from app.core.security import get_password_hash, create_access_token

@pytest.fixture
def readiness_setup(db):
    org = Organization(
        name="Pilot Readiness Org",
        organization_type=OrganizationType.NGO,
        email="ready@pilot.org",
        phone="+919847555555",
        operating_region="Central Hub",
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    ngo_admin = User(
        full_name="Readiness Admin",
        email="admin@pilot.org",
        phone="+919847555556",
        password_hash=get_password_hash("password123"),
        role=UserRole.NGO_ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    rescuer = User(
        full_name="Active Rescuer",
        email="rescuer@pilot.org",
        phone="+919847555557",
        password_hash=get_password_hash("password123"),
        role=UserRole.RESCUER,
        organization_id=org.id,
        is_active=True,
    )
    vet = User(
        full_name="Active Vet",
        email="vet@pilot.org",
        phone="+919847555558",
        password_hash=get_password_hash("password123"),
        role=UserRole.VETERINARIAN,
        organization_id=org.id,
        is_active=True,
    )
    super_admin = User(
        full_name="Super Admin",
        email="superadmin@pilot.org",
        phone="+919847555559",
        password_hash=get_password_hash("password123"),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    db.add_all([ngo_admin, rescuer, vet, super_admin])
    db.commit()
    db.refresh(rescuer)

    rescuer_profile = RescuerProfile(
        user_id=rescuer.id,
        organization_id=org.id,
        availability_status=RescuerAvailability.AVAILABLE,
        latitude=9.9816,
        longitude=76.2999,
        last_location_update=datetime.utcnow(),
    )
    db.add(rescuer_profile)

    fac = VeterinaryFacility(
        name="Pilot Partner Clinic",
        phone="+91484999999",
        latitude=9.9816,
        longitude=76.2999,
        organization_id=org.id,
        is_verified=True,
    )
    db.add(fac)
    db.commit()

    return {
        "org": org,
        "admin_token": create_access_token(ngo_admin.id),
        "rescuer_token": create_access_token(rescuer.id),
        "rescuer_id": rescuer.id,
        "vet_token": create_access_token(vet.id),
        "super_token": create_access_token(super_admin.id),
    }

def test_upload_image_endpoint(client, readiness_setup):
    img_byte_arr = io.BytesIO()
    image = Image.new("RGB", (200, 200), color="blue")
    image.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)

    files = {"file": ("test_rescue.jpg", img_byte_arr, "image/jpeg")}
    headers = {"Authorization": f"Bearer {readiness_setup['rescuer_token']}"}

    res = client.post("/api/v1/uploads/image", files=files, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "image_url" in data
    assert data["filename"] == "test_rescue.jpg"

def test_animal_crud_endpoints(client, readiness_setup):
    super_headers = {"Authorization": f"Bearer {readiness_setup['super_token']}"}
    vet_headers = {"Authorization": f"Bearer {readiness_setup['vet_token']}"}

    # 1. Non-superadmin cannot create standalone animals (403)
    denied_create = client.post(
        "/api/v1/animals",
        json={"species": "Dog", "sex": "Male", "description": "Brown stray puppy"},
        headers=vet_headers
    )
    assert denied_create.status_code == 403

    # 2. Superadmin creates standalone animal (200)
    create_res = client.post(
        "/api/v1/animals",
        json={"species": "Dog", "sex": "Male", "description": "Brown stray puppy"},
        headers=super_headers
    )
    assert create_res.status_code == 200
    animal = create_res.json()
    assert animal["species"] == "Dog"
    assert animal["description"] == "Brown stray puppy"
    animal_id = animal["id"]

    # 3. Non-superadmin cannot read or patch standalone animal (403)
    assert client.get(f"/api/v1/animals/{animal_id}", headers=vet_headers).status_code == 403
    assert client.patch(f"/api/v1/animals/{animal_id}", json={"description": "Hacked"}, headers=vet_headers).status_code == 403

    # 4. Superadmin can get and patch standalone animal (200)
    get_res = client.get(f"/api/v1/animals/{animal_id}", headers=super_headers)
    assert get_res.status_code == 200
    assert get_res.json()["species"] == "Dog"

    patch_res = client.patch(
        f"/api/v1/animals/{animal_id}",
        json={"description": "Brown stray puppy - vaccinated"},
        headers=super_headers
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["description"] == "Brown stray puppy - vaccinated"

def test_rescuer_profile_and_location_endpoints(client, readiness_setup):
    headers = {"Authorization": f"Bearer {readiness_setup['rescuer_token']}"}

    # Get profile
    res_prof = client.get("/api/v1/rescuers/me/profile", headers=headers)
    assert res_prof.status_code == 200
    assert res_prof.json()["availability_status"] == "AVAILABLE"

    # Update location
    res_loc = client.patch("/api/v1/rescuers/me/location", json={"latitude": 10.015, "longitude": 76.341}, headers=headers)
    assert res_loc.status_code == 200
    assert res_loc.json()["latitude"] == 10.015

    # Update availability
    res_avail = client.patch("/api/v1/rescuers/me/availability", json={"availability_status": "BUSY"}, headers=headers)
    assert res_avail.status_code == 200
    assert res_avail.json()["availability_status"] == "BUSY"

def test_ngo_responders_and_veterinary_roster(client, readiness_setup):
    headers = {"Authorization": f"Bearer {readiness_setup['admin_token']}"}

    # Responders
    resp_res = client.get("/api/v1/ngo/responders", headers=headers)
    assert resp_res.status_code == 200
    responders = resp_res.json()
    assert len(responders) >= 1
    assert any(r["full_name"] == "Active Rescuer" for r in responders)

    # Patch responder status
    patch_res = client.patch(
        f"/api/v1/ngo/responders/{readiness_setup['rescuer_id']}/status",
        json={"is_active": True, "reliability_score": 95.0},
        headers=headers,
    )
    assert patch_res.status_code == 200

    # Veterinary
    vet_res = client.get("/api/v1/ngo/veterinary", headers=headers)
    assert vet_res.status_code == 200
    facilities = vet_res.json()
    assert len(facilities) >= 1
    assert any(f["name"] == "Pilot Partner Clinic" for f in facilities)
