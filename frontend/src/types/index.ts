export type UserRole = 'CITIZEN' | 'RESCUER' | 'VETERINARIAN' | 'NGO_ADMIN' | 'SUPER_ADMIN' | 'MUNICIPAL_ADMIN' | 'FOSTER';

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
  urgent_cases?: number;
  searching_responder_cases?: number;
  awaiting_responder: number;
  responders_en_route: number;
  responders_available?: number;
  responders_assigned?: number;
  under_treatment: number;
  recovering: number;
  unresolved_cases?: number;
  closed_today?: number;
  avg_dispatch_seconds: number;
  average_response_minutes: number | null;
  avg_completion_minutes?: number;
  completion_rate_pct: number;
  responder_availability_pct: number;
  total_cases: number;
  average_dispatch_latency_seconds?: number | null;
  average_acceptance_latency_seconds?: number | null;
  average_arrival_minutes?: number | null;
  average_rescue_duration_minutes?: number | null;
  average_case_completion_minutes?: number | null;
}

export interface HotspotItem {
  latitude: number;
  longitude: number;
  area_name?: string;
  incident_count: number;
  critical_count: number;
  urgent_count?: number;
  top_species: string;
  average_response_minutes: number | null;
  average_acceptance_minutes?: number | null;
  average_arrival_minutes?: number | null;
}

export interface ResponseTimeDataPoint {
  date: string;
  average_response_minutes: number | null;
  cases: number;
}

export interface RescueOutcomesData {
  outcomes: Record<string, number>;
  rescue_success_rate: number;
  unresolved_rate: number;
  veterinary_handoff_rate: number;
  total_cases: number;
  active_field_count?: number;
  rescued_transport_count?: number;
  medical_care_count?: number;
  post_care_count?: number;
  successful_terminal_count?: number;
  failure_count?: number;
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

export interface ServiceHealth {
  database: string;
  postgis?: string;
  redis: string;
  celery: string;
  storage: string;
  firebase: string;
}

export interface HealthReadinessResponse {
  status: 'ready' | 'degraded' | 'offline';
  environment: string;
  services: ServiceHealth;
  checks?: Record<string, string>;
}

// ==========================================
// PHASE 3A: FOSTER & ADOPTION INTERFACES
// ==========================================

export type FosterHomeAvailability = 'AVAILABLE' | 'FULL' | 'TEMPORARILY_UNAVAILABLE' | 'INACTIVE';
export type FosterAssignmentStatus = 'OFFERED' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED' | 'TRANSFERRED';
export type AdoptionListingStatus = 'DRAFT' | 'PUBLISHED' | 'PENDING' | 'ADOPTED' | 'CLOSED' | 'WITHDRAWN';
export type AdoptionApplicationStatus = 'SUBMITTED' | 'UNDER_REVIEW' | 'VISIT_SCHEDULED' | 'APPROVED' | 'REJECTED' | 'WITHDRAWN';
export type AdoptionVisitStatus = 'SCHEDULED' | 'COMPLETED' | 'CANCELLED' | 'RESCHEDULED';

export interface FosterCareUpdate {
  id: string;
  assignment_id: string;
  update_type?: string;
  notes?: string;
  general_notes?: string;
  appetite_status?: string;
  mobility_status?: string;
  medication_administered: boolean;
  behavioral_notes?: string;
  media_urls?: string[];
  created_at: string;
}

export interface FosterAssignment {
  id: string;
  animal_id?: string;
  rescue_case_id?: string;
  foster_home_id: string;
  status: FosterAssignmentStatus;
  start_date?: string;
  expected_end_date?: string;
  actual_end_date?: string;
  notes?: string;
  created_at?: string;
  case_number?: string;
  animal_species?: string;
  animal_description?: string;
  rescue_case?: {
    id: string;
    case_number: string;
    species: string;
    description?: string;
    status: RescueStatus;
  };
  care_updates?: FosterCareUpdate[];
}

export interface FosterHome {
  id: string;
  caregiver_id: string;
  organization_id?: string;
  locality?: string;
  latitude?: number;
  longitude?: number;
  capacity: number;
  current_occupancy: number;
  accepted_species?: string;
  medical_care_supported: boolean;
  availability_status: FosterHomeAvailability;
  verified: boolean;
  verified_at?: string;
  created_at?: string;
  caregiver?: {
    id: string;
    full_name: string;
    phone?: string;
    email?: string;
  };
  active_assignments?: FosterAssignment[];
}

export interface FosterCandidate {
  foster_home_id: string;
  caregiver_name: string;
  locality: string;
  score: number;
  compatible: boolean;
  reasons: string[];
  remaining_capacity: number;
  distance_km?: number;
}

export interface AdoptionListing {
  id: string;
  animal_id: string;
  rescue_case_id: string;
  organization_id: string;
  title: string;
  public_description?: string;
  public_image_url?: string;
  species: string;
  sex?: string;
  approx_age?: string;
  colour?: string;
  identifying_marks?: string;
  sterilization_status?: string;
  vaccination_status?: string;
  medical_summary?: string;
  organization_name: string;
  organization_email?: string;
  organization_phone?: string;
  locality?: string;
  status: AdoptionListingStatus;
  published_at?: string;
  created_at?: string;
}

export interface AdoptionVisit {
  id: string;
  application_id: string;
  scheduled_at: string;
  visit_type: string;
  location_address: string;
  notes?: string;
  status: AdoptionVisitStatus;
  created_at?: string;
}

export interface AdoptionApplication {
  id: string;
  listing_id: string;
  applicant_id: string;
  status: AdoptionApplicationStatus;
  housing_type?: string;
  has_fenced_garden: boolean;
  has_other_pets: boolean;
  family_members_count?: number;
  experience_with_pets?: string;
  reason_for_adoption?: string;
  reviewer_notes?: string;
  rejection_reason?: string;
  reviewed_at?: string;
  created_at?: string;
  listing_title?: string;
  animal_species?: string;
  listing?: AdoptionListing;
  applicant?: {
    id: string;
    full_name: string;
    phone?: string;
    email?: string;
  };
  visits?: AdoptionVisit[];
}



