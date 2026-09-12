from enum import Enum
from typing import Dict, List

class UserRole(str, Enum):
    CITIZEN = "CITIZEN"
    RESCUER = "RESCUER"
    VETERINARIAN = "VETERINARIAN"
    NGO_ADMIN = "NGO_ADMIN"
    MUNICIPAL_ADMIN = "MUNICIPAL_ADMIN"
    FOSTER = "FOSTER"
    SUPER_ADMIN = "SUPER_ADMIN"

class OrganizationType(str, Enum):
    NGO = "NGO"
    VETERINARY_CLINIC = "VETERINARY_CLINIC"
    ANIMAL_HOSPITAL = "ANIMAL_HOSPITAL"
    MUNICIPALITY = "MUNICIPALITY"
    SHELTER = "SHELTER"
    RESCUE_NETWORK = "RESCUE_NETWORK"

class RescuePriority(str, Enum):
    GENERAL = "GENERAL"
    MODERATE = "MODERATE"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"

class RescueStatus(str, Enum):
    REPORTED = "REPORTED"
    TRIAGED = "TRIAGED"
    SEARCHING_RESPONDER = "SEARCHING_RESPONDER"
    RESPONDER_ASSIGNED = "RESPONDER_ASSIGNED"
    RESPONDER_EN_ROUTE = "RESPONDER_EN_ROUTE"
    ANIMAL_LOCATED = "ANIMAL_LOCATED"
    RESCUED = "RESCUED"
    TRANSPORTING = "TRANSPORTING"
    AT_VETERINARY_FACILITY = "AT_VETERINARY_FACILITY"
    UNDER_TREATMENT = "UNDER_TREATMENT"
    RECOVERING = "RECOVERING"
    FOSTER_CARE = "FOSTER_CARE"
    READY_FOR_RELEASE = "READY_FOR_RELEASE"
    READY_FOR_ADOPTION = "READY_FOR_ADOPTION"
    RELEASED = "RELEASED"
    ADOPTED = "ADOPTED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    UNRESOLVED = "UNRESOLVED"

class RescuerAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"

class AssignmentStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"

ALLOWED_STATUS_TRANSITIONS: Dict[RescueStatus, List[RescueStatus]] = {
    RescueStatus.REPORTED: [RescueStatus.TRIAGED, RescueStatus.CANCELLED],
    RescueStatus.TRIAGED: [RescueStatus.SEARCHING_RESPONDER, RescueStatus.RESPONDER_ASSIGNED, RescueStatus.CANCELLED],
    RescueStatus.SEARCHING_RESPONDER: [RescueStatus.RESPONDER_ASSIGNED, RescueStatus.UNRESOLVED, RescueStatus.CANCELLED],
    RescueStatus.RESPONDER_ASSIGNED: [RescueStatus.RESPONDER_EN_ROUTE, RescueStatus.CANCELLED, RescueStatus.SEARCHING_RESPONDER],
    RescueStatus.RESPONDER_EN_ROUTE: [RescueStatus.ANIMAL_LOCATED, RescueStatus.UNRESOLVED, RescueStatus.CANCELLED],
    RescueStatus.ANIMAL_LOCATED: [RescueStatus.RESCUED, RescueStatus.UNRESOLVED, RescueStatus.CANCELLED],
    RescueStatus.RESCUED: [RescueStatus.TRANSPORTING, RescueStatus.UNRESOLVED],
    RescueStatus.TRANSPORTING: [RescueStatus.AT_VETERINARY_FACILITY, RescueStatus.UNRESOLVED],
    RescueStatus.AT_VETERINARY_FACILITY: [RescueStatus.UNDER_TREATMENT, RescueStatus.UNRESOLVED],
    RescueStatus.UNDER_TREATMENT: [RescueStatus.RECOVERING, RescueStatus.UNRESOLVED],
    RescueStatus.RECOVERING: [RescueStatus.FOSTER_CARE, RescueStatus.READY_FOR_RELEASE, RescueStatus.READY_FOR_ADOPTION, RescueStatus.CLOSED],
    RescueStatus.FOSTER_CARE: [RescueStatus.READY_FOR_ADOPTION, RescueStatus.READY_FOR_RELEASE, RescueStatus.ADOPTED, RescueStatus.CLOSED],
    RescueStatus.READY_FOR_RELEASE: [RescueStatus.RELEASED],
    RescueStatus.READY_FOR_ADOPTION: [RescueStatus.ADOPTED],
    RescueStatus.RELEASED: [RescueStatus.CLOSED],
    RescueStatus.ADOPTED: [RescueStatus.CLOSED],
    RescueStatus.CLOSED: [],
    RescueStatus.CANCELLED: [],
    RescueStatus.UNRESOLVED: [RescueStatus.SEARCHING_RESPONDER, RescueStatus.CLOSED, RescueStatus.CANCELLED],
}

STATUS_ROLE_PERMISSIONS: Dict[UserRole, List[RescueStatus]] = {
    UserRole.RESCUER: [
        RescueStatus.RESPONDER_ASSIGNED,
        RescueStatus.RESPONDER_EN_ROUTE,
        RescueStatus.ANIMAL_LOCATED,
        RescueStatus.RESCUED,
        RescueStatus.TRANSPORTING,
        RescueStatus.AT_VETERINARY_FACILITY,
        RescueStatus.UNRESOLVED,
    ],
    UserRole.VETERINARIAN: [
        RescueStatus.UNDER_TREATMENT,
        RescueStatus.RECOVERING,
        RescueStatus.READY_FOR_RELEASE,
        RescueStatus.READY_FOR_ADOPTION,
        RescueStatus.RELEASED,
        RescueStatus.ADOPTED,
        RescueStatus.CLOSED,
    ],
    UserRole.CITIZEN: [
        RescueStatus.CANCELLED,
    ],
    UserRole.NGO_ADMIN: list(RescueStatus),
    UserRole.SUPER_ADMIN: list(RescueStatus),
    UserRole.MUNICIPAL_ADMIN: list(RescueStatus),
    UserRole.FOSTER: [
        RescueStatus.FOSTER_CARE,
        RescueStatus.READY_FOR_ADOPTION,
    ],
}
