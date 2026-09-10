from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from app.database import get_db
from app.models.user import User
from app.models.treatment import Treatment
from app.models.rescue_case import RescueCase
from app.schemas.veterinary import TreatmentCreate, TreatmentUpdate, TreatmentResponse
from app.core.permissions import RoleChecker
from app.core.constants import UserRole, RescueStatus
from app.core.exceptions import NotFoundException
from app.services.rescue_service import RescueService
from datetime import datetime

router = APIRouter()

@router.post("", response_model=TreatmentResponse)
def add_treatment(
    case_id: UUID,
    treatment_in: TreatmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.VETERINARIAN]))
):
    case = db.query(RescueCase).filter(RescueCase.id == case_id).first()
    if not case:
        raise NotFoundException("Rescue case not found")
        
    treatment = Treatment(
        rescue_case_id=case.id,
        animal_id=case.animal_id,
        veterinarian_id=current_user.id,
        facility_id=treatment_in.facility_id,
        diagnosis=treatment_in.diagnosis,
        treatment_notes=treatment_in.treatment_notes,
        medications=treatment_in.medications,
    )
    db.add(treatment)
    
    # Update case status to UNDER_TREATMENT
    if case.status != RescueStatus.UNDER_TREATMENT:
        RescueService.update_status(db, case, RescueStatus.UNDER_TREATMENT, current_user.id, "Treatment started")
        
    db.commit()
    db.refresh(treatment)
    return treatment

@router.get("", response_model=List[TreatmentResponse])
def get_treatments(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.VETERINARIAN, UserRole.RESCUER, UserRole.NGO_ADMIN]))
):
    treatments = db.query(Treatment).filter(Treatment.rescue_case_id == case_id).all()
    return treatments

@router.patch("/{treatment_id}", response_model=TreatmentResponse)
def update_treatment(
    treatment_id: UUID,
    treatment_in: TreatmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.VETERINARIAN]))
):
    treatment = db.query(Treatment).filter(Treatment.id == treatment_id).first()
    if not treatment:
        raise NotFoundException("Treatment not found")
        
    for key, value in treatment_in.dict(exclude_unset=True).items():
        setattr(treatment, key, value)
        
    db.commit()
    db.refresh(treatment)
    return treatment
