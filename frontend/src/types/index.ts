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
  | 'FOSTERED' 
  | 'RELEASED' 
  | 'ADOPTED' 
  | 'CLOSED' 
  | 'CANCELLED';

export type RescuePriority = 'CRITICAL' | 'URGENT' | 'MODERATE' | 'GENERAL' | 'LOW';

export interface RescueCase {
  id: string;
  case_number: string;
  species: string;
  description: string;
  latitude: number;
  longitude: number;
  address_text: string;
  triage_score: number;
  triage_priority: RescuePriority;
  triage_reason: string;
  status: RescueStatus;
  created_at: string;
  updated_at: string;
  reporter_id: string;
}

export interface RescueTimeline {
  id: string;
  previous_status?: RescueStatus;
  new_status: RescueStatus;
  notes?: string;
  created_at: string;
}
