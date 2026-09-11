export type UserRole = 'CITIZEN' | 'RESCUER' | 'VETERINARIAN' | 'NGO_ADMIN' | 'SUPER_ADMIN' | 'MUNICIPAL_ADMIN';

export interface User {
  id: string;
  full_name: string;
  email?: string;
  phone: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  organization_id?: string;
}

export type RescueStatus = 
  | 'REPORTED' 
  | 'TRIAGED' 
  | 'SEARCHING_RESPONDER' 
  | 'RESPONDER_ASSIGNED' 
  | 'RESPONDER_EN_ROUTE' 
  | 'ANIMAL_LOCATED' 
  | 'RESCUED' 
  | 'TRANSPORTING' 
  | 'AT_VETERINARY_FACILITY' 
  | 'UNDER_TREATMENT' 
  | 'RECOVERING' 
  | 'FOSTER_CARE' 
  | 'READY_FOR_RELEASE' 
  | 'READY_FOR_ADOPTION' 
  | 'RELEASED' 
  | 'ADOPTED' 
  | 'CLOSED' 
  | 'CANCELLED'
  | 'UNRESOLVED';

export type RescuePriority = 'CRITICAL' | 'URGENT' | 'MODERATE' | 'GENERAL';

export interface AnimalImage {
  id: string;
  image_url: string;
  image_type: string;
  created_at: string;
}

export interface AssignedResponder {
  id: string;
  full_name: string;
  assignment_status: string;
  accepted_at?: string;
}

export interface VeterinaryFacility {
  id: string;
  name: string;
  phone?: string;
  email?: string;
  address?: string;
  latitude: number;
  longitude: number;
  supports_emergency: boolean;
  is_24_hours: boolean;
  is_verified: boolean;
}

export interface RescueCase {
  id: string;
  case_number: string;
  animal_id?: string;
  species: string;
  description: string;
  latitude: number;
  longitude: number;
  address_text: string;
  triage_score: number;
  triage_priority: RescuePriority;
  triage_reason: string;
  status: RescueStatus;
  veterinary_facility_id?: string;
  created_at: string;
  updated_at: string;
  closed_at?: string;
  reporter_id: string;
  distance_km?: number;
  images?: AnimalImage[];
  assigned_responder?: AssignedResponder;
}

export interface RescueTimeline {
  id: string;
  previous_status?: RescueStatus;
  new_status: RescueStatus;
  notes?: string;
  created_at: string;
}
