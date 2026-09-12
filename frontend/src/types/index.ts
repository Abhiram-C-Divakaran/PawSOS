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

export interface DispatchOffer {
  id: string;
  rescue_case_id: string;
  rescuer_id: string;
  assignment_status: 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'EXPIRED' | 'CANCELLED' | 'COMPLETED';
  distance_km?: number;
  dispatch_score?: number;
  offered_at?: string;
  expires_at?: string;
  accepted_at?: string;
  rejected_at?: string;
  rejection_reason?: string;
  case?: {
    id: string;
    case_number: string;
    species: string;
    description?: string;
    latitude: number;
    longitude: number;
    address_text?: string;
    triage_priority: RescuePriority;
    triage_score: number;
    triage_reason?: string;
    status: RescueStatus;
    created_at: string;
    image_url?: string;
  };
}

export interface NotificationItem {
  id: string;
  user_id: string;
  type: string;
  title: string;
  message: string;
  rescue_case_id?: string;
  data?: string;
  is_read: boolean;
  created_at: string;
  read_at?: string;
}

export interface NGOOverviewKPIs {
  active_cases: number;
  critical_cases: number;
  awaiting_responder: number;
  responders_en_route: number;
  under_treatment: number;
  recovering: number;
  avg_dispatch_seconds: number;
  avg_response_minutes: number;
  completion_rate_pct: number;
  responder_availability_pct: number;
  total_cases: number;
}

export interface HotspotItem {
  latitude: number;
  longitude: number;
  area_name?: string;
  incident_count: number;
  critical_count: number;
  urgent_count?: number;
  top_species: string;
  average_response_minutes?: number;
}

export interface ResponseTimeDataPoint {
  date: string;
  avg_response_minutes: number;
  cases: number;
}

export interface RescueOutcomesData {
  outcomes: Record<string, number>;
  rescue_success_rate: number;
  unresolved_rate: number;
  veterinary_handoff_rate: number;
  total_cases: number;
}

export interface NGOInsightsData {
  busiest_day: string | null;
  busiest_time_range: string | null;
  top_rescue_area: string | null;
  responder_acceptance_rate_pct: number;
  avg_dispatch_attempts: number;
  escalation_rate_pct: number;
}

export interface OrganizationProfile {
  id: string;
  name: string;
  organization_type: string;
  email?: string;
  phone?: string;
  address?: string;
  operating_region?: string;
  description?: string;
  responders_count: number;
  veterinary_partners_count: number;
  created_at?: string;
  is_active: boolean;
}

export interface OrganizationProfileUpdate {
  name?: string;
  email?: string;
  phone?: string;
  address?: string;
  operating_region?: string;
  description?: string;
}

export interface DispatchSettings {
  default_radius_km: number;
  radius_escalation_levels: number[];
  offer_expiration_seconds: number;
  stale_location_timeout_seconds: number;
}

export interface NotificationPreferences {
  critical_rescue_alerts: boolean;
  dispatch_failures: boolean;
  veterinary_updates: boolean;
  case_closures: boolean;
}

export interface NGOResponderSummary {
  id: string;
  user_id: string;
  full_name: string;
  phone: string;
  email?: string;
  is_active: boolean;
  availability_status: 'AVAILABLE' | 'BUSY' | 'OFFLINE';
  latitude?: number;
  longitude?: number;
  last_location_update?: string;
  vehicle_available: boolean;
  experience_level: string;
  reliability_score: number;
  completed_rescues: number;
  total_offers: number;
  accepted_offers: number;
  acceptance_rate_pct: number;
  active_case_number?: string;
}

export interface AuditLogItem {
  id: string;
  actor_id?: string;
  action: string;
  entity: string;
  entity_id?: string;
  old_value?: Record<string, any>;
  new_value?: Record<string, any>;
  timestamp: string;
}


