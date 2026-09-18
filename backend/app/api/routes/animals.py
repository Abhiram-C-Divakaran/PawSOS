from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.models.user import User
from app.models.animal import Animal
from app.schemas.animal import AnimalCreate, AnimalUpdate, AnimalResponse
from app.core.permissions import RoleChecker
from app.core.constants import UserRole
from app.core.exceptions import NotFoundException
from app.core.case_access import verify_animal_access

router = APIRouter()

@router.post("", response_model=AnimalResponse)
def create_animal(
    animal_in: AnimalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.VETERINARIAN, UserRole.RESCUER, UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    animal = Animal(**animal_in.dict(exclude_unset=True))
    db.add(animal)
    db.commit()
    db.refresh(animal)
    return animal

@router.get("/{animal_id}", response_model=AnimalResponse)
def get_animal(
    animal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.VETERINARIAN, UserRole.RESCUER, UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    animal = db.query(Animal).filter(Animal.id == animal_id).first()
    if not animal:
        raise NotFoundException("Animal not found")
    verify_animal_access(animal, current_user, db)
    return animal

@router.patch("/{animal_id}", response_model=AnimalResponse)
def update_animal(
    animal_id: UUID,
    animal_in: AnimalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.VETERINARIAN, UserRole.RESCUER, UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]))
):
    animal = db.query(Animal).filter(Animal.id == animal_id).first()
    if not animal:
        raise NotFoundException("Animal not found")
    verify_animal_access(animal, current_user, db)
        
    for key, value in animal_in.dict(exclude_unset=True).items():
        setattr(animal, key, value)
        
    db.commit()
    db.refresh(animal)
    return animal
