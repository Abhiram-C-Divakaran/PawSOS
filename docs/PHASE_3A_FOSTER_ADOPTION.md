# PawReach Phase 3A — Foster & Adoption Operations

> [!NOTE]
> **Implementation Status**: Phase 3A Foster & Adoption operations are fully implemented, certified, and validated in CI and live staging. For live deployment architecture, refer to [LIVE_STAGING_VALIDATION.md](LIVE_STAGING_VALIDATION.md) and [FREE_DEPLOYMENT.md](FREE_DEPLOYMENT.md).

## 1. Executive Summary & Operational Scope

Phase 3A extends the **PawReach** animal rescue coordination platform beyond acute incident response and veterinary treatment into an end-to-end post-treatment care and permanent placement continuum:

```text
RECOVERING
   │
   ├───────────────────────────────┐
   ▼                               ▼
FOSTER_CARE                 READY_FOR_ADOPTION
   │                               │
   ├───────────────┐               ▼
   ▼               ▼        ADOPTION_LISTING (Published)
READY_FOR_    READY_FOR_           │
 RELEASE      ADOPTION             ▼
   │               │        CITIZEN_APPLICATION
   ▼               ▼               │
RELEASED        ADOPTED            ▼
   │               │        NGO_REVIEW / VISIT
   └───────┬───────┘               │
           ▼                       ▼
        CLOSED                  ADOPTED (Cascade)
```

Phase 3A builds comprehensive operational modules for:
1. **Foster Caregiver Management**: Verified caregiver profiles, capacity limits, species and medical specialization preferences, and privacy-shielded location handling.
2. **Deterministic Foster Matching & Placement**: Matching algorithms scoring locality proximity, species suitability, medical capability, and available capacity; formal offer dispatch with explicit caregiver acceptance/declination and atomic occupancy updates.
3. **Foster Care Tracking**: Daily wellbeing observation logs (appetite, mobility, medication, behavioral notes) with release/adoption readiness recommendations.
4. **Adoption Public Catalog**: Sanitized public listings for fully rehabilitated animals (`READY_FOR_ADOPTION`), preventing premature listings and hiding sensitive reporter and caregiver coordinates.
5. **Adoption Application & Lifecycle Management**: Citizen applications, NGO multi-stage review (submission, under-review, visit scheduling, home checks), and transactional cascade approvals (`with_for_update`) that atomically approve applications, close listings, transition case status to `ADOPTED`, auto-reject pending applicants, and complete active foster assignments.

---

## 2. Architecture & Data Model

### 2.1 Database Entities & Relationships

```
┌─────────────────┐       1:N      ┌─────────────────────────┐
│  Organization   │───────────────▶│       FosterHome        │
└─────────────────┘                └─────────────────────────┘
                                                │ 1
                                                ▼ N
┌─────────────────┐       1:N      ┌─────────────────────────┐
│   RescueCase    │───────────────▶│    FosterAssignment     │
└─────────────────┘                └─────────────────────────┘
        │ 1                                     │ 1
        │                                       ▼ N
        │ 1:1                              ┌─────────────────────────┐
        ▼                                  │    FosterCareUpdate     │
┌─────────────────┐                        └─────────────────────────┘
│ AdoptionListing │
└─────────────────┘
        │ 1
        ▼ N
┌─────────────────────┐   1:N      ┌─────────────────────────┐
│ AdoptionApplication │───────────▶│      AdoptionVisit      │
└─────────────────────┘            └─────────────────────────┘
```

1. **`FosterHome`** (`foster_homes`):
   - `id`: UUID (PK)
   - `caregiver_id`: UUID (FK `users.id`)
   - `organization_id`: UUID (FK `organizations.id`, nullable for open network)
   - `locality`: String (publicly exposed neighborhood name, e.g., "Bandra West")
   - `latitude`, `longitude`: Float (private, never exposed to public or non-staff)
   - `capacity`: Integer (>= 1, enforced via check constraint)
   - `current_occupancy`: Integer (0 <= current_occupancy <= capacity)
   - `accepted_species`: String (comma-delimited, e.g. "Canine,Feline")
   - `maximum_animal_size`: String ("Small", "Medium", "Large", "Giant")
   - `medical_care_supported`: Boolean
   - `availability_status`: String ("AVAILABLE", "FULL", "UNAVAILABLE")
   - `verified`: Boolean (requires NGO / SuperAdmin verification)
   - `verified_at`, `verified_by_user_id`: Timestamp & User FK

2. **`FosterAssignment`** (`foster_assignments`):
   - `id`: UUID (PK)
   - `rescue_case_id`: UUID (FK `rescue_cases.id`)
   - `foster_home_id`: UUID (FK `foster_homes.id`)
   - `status`: String ("OFFERED", "ACTIVE", "COMPLETED", "CANCELLED", "DECLINED")
   - `offered_at`, `expires_at`: Timestamps for assignment lifecycle
   - `start_date`, `end_date`: Placed interval
   - `notes`: Text instructions

3. **`FosterCareUpdate`** (`foster_care_updates`):
   - `id`: UUID (PK)
   - `assignment_id`: UUID (FK `foster_assignments.id`)
   - `created_by`: UUID (FK `users.id`)
   - `created_at`: Timestamp
   - `notes`: Text (care observations)
   - `appetite_status`: String ("Normal", "Reduced", "Increased", "Refusing Food")
   - `mobility_status`: String ("Normal", "Limping", "Restricted", "Non-ambulatory")
   - `medication_administered`: Boolean
   - `behavioral_notes`: String
   - `readiness_recommendation`: String ("CONTINUE_FOSTER", "READY_FOR_RELEASE", "READY_FOR_ADOPTION")

4. **`AdoptionListing`** (`adoption_listings`):
   - `id`: UUID (PK)
   - `animal_id`: UUID (FK `animals.id`)
   - `rescue_case_id`: UUID (FK `rescue_cases.id`)
   - `organization_id`: UUID (FK `organizations.id`)
   - `title`: String
   - `public_description`: Text
   - `public_image_url`: String
   - `status`: String ("DRAFT", "PUBLISHED", "PAUSED", "CLOSED")
   - `published_at`, `closed_at`: Timestamps
   - `created_by`: UUID (FK `users.id`)

5. **`AdoptionApplication`** (`adoption_applications`):
   - `id`: UUID (PK)
   - `listing_id`: UUID (FK `adoption_listings.id`)
   - `applicant_id`: UUID (FK `users.id`)
   - `organization_id`: UUID (FK `organizations.id`)
   - `housing_type`: String ("Apartment", "Independent House", "Villa", "Farmhouse")
   - `family_members_count`: Integer
   - `has_fenced_garden`: Boolean
   - `has_other_pets`: Boolean
   - `experience_with_pets`: Text
   - `reason_for_adoption`: Text
   - `status`: String ("SUBMITTED", "UNDER_REVIEW", "VISIT_SCHEDULED", "HOME_CHECK_PENDING", "APPROVED", "REJECTED", "WITHDRAWN")
   - `review_notes`: Text
   - `reviewed_by`: UUID (FK `users.id`)

6. **`AdoptionVisit`** (`adoption_visits`):
   - `id`: UUID (PK)
   - `application_id`: UUID (FK `adoption_applications.id`)
   - `visit_date`: Timestamp
   - `location_type`: String ("FACILITY", "FOSTER_HOME", "APPLICANT_HOME")
   - `visit_address`: String
   - `status`: String ("SCHEDULED", "COMPLETED", "CANCELLED")
   - `outcome_notes`: Text

---

## 3. API Surface

### 3.1 Foster Operations (`/api/v1/foster`)

| Method | Endpoint | Access / Roles | Description |
|---|---|---|---|
| `GET` | `/profile` | `FOSTER`, Staff | Get current user's foster home profile |
| `POST` | `/profile` | `FOSTER`, Staff | Create or update foster home profile |
| `GET` | `/matches/{case_id}` | `NGO_ADMIN`, `SUPER_ADMIN` | Deterministic ranking of verified foster homes for case |
| `POST` | `/assignments/offer` | `NGO_ADMIN`, `SUPER_ADMIN` | Dispatch foster placement offer |
| `POST` | `/assignments/{id}/accept` | Caregiver (`FOSTER`) | Accept offer; increments occupancy & sets case to `FOSTER_CARE` |
| `POST` | `/assignments/{id}/decline` | Caregiver (`FOSTER`) | Decline offer; frees assignment |
| `GET` | `/assignments/my` | Caregiver (`FOSTER`) | List incoming offers and active placements |
| `POST` | `/assignments/{id}/updates` | Caregiver (`FOSTER`) | Record daily care log & readiness observation |
| `GET` | `/assignments/{id}/updates` | Caregiver, Staff | View care logs for placement |
| `POST` | `/assignments/{id}/status` | Staff | Complete or cancel foster assignment |
| `POST` | `/verify/{home_id}` | `NGO_ADMIN`, `SUPER_ADMIN` | Verify caregiver home & grant placement eligibility |

### 3.2 Adoption Operations (`/api/v1/adoptions`)

| Method | Endpoint | Access / Roles | Description |
|---|---|---|---|
| `GET` | `/listings` | Public (Unauthenticated) | Sanitized public catalog of published listings |
| `GET` | `/listings/{id}` | Public (Unauthenticated) | Public profile with medical clearance & organization info |
| `POST` | `/listings` | `NGO_ADMIN`, `SUPER_ADMIN` | Create listing (requires case status `READY_FOR_ADOPTION`) |
| `PATCH`| `/listings/{id}/status` | `NGO_ADMIN`, `SUPER_ADMIN` | Transition listing status (`PUBLISHED`, `PAUSED`, `CLOSED`) |
| `POST` | `/applications` | Authenticated (`CITIZEN`) | Submit adoption application |
| `GET` | `/applications/my` | Authenticated (`CITIZEN`) | Track personal adoption applications & scheduled visits |
| `POST` | `/applications/{id}/withdraw` | Applicant (`CITIZEN`) | Withdraw active application |
| `GET` | `/applications` | `NGO_ADMIN`, `SUPER_ADMIN` | Multi-tenant inbox for organization applications |
| `POST` | `/applications/{id}/schedule-visit`| `NGO_ADMIN`, `SUPER_ADMIN` | Schedule meet-and-greet or home check visit |
| `POST` | `/applications/{id}/decision` | `NGO_ADMIN`, `SUPER_ADMIN` | Concurrency-safe approval/rejection cascade |

---

## 4. Privacy, Tenant Scoping & Concurrency Safety

1. **Location Privacy Protection**:
   - Caregiver exact GPS coordinates (`latitude`, `longitude`) are strictly masked on all non-administrative and public endpoints. Only general `locality` (e.g. "Bandra West") is visible.
   - Public adoption listings expose animal narrative and organization contact; original incident reporter details (phone, email, exact location) are fully stripped.

2. **Multi-Tenant NGO Isolation**:
   - NGO admins and staff can only manage listings, review applications, and dispatch foster offers within their organization's tenant boundary.
   - Attempting cross-tenant access returns an explicit `403 Forbidden` or `404 Not Found`.

3. **Concurrency-Safe Atomic Cascades (`with_for_update`)**:
   - `FosterService.accept_assignment` locks both `FosterAssignment` and `FosterHome` records before verifying remaining capacity and incrementing occupancy.
   - `AdoptionService.process_decision` locks the `AdoptionApplication`, `AdoptionListing`, and underlying `RescueCase` with `with_for_update()`.
   - On `APPROVED`:
     - Application status transitions to `APPROVED`.
     - Listing status transitions to `CLOSED`.
     - Underlying rescue case status transitions to `ADOPTED`.
     - All other pending applications for this listing are automatically transitioned to `REJECTED`.
     - Any active foster placement for this animal is cleanly finalized to `COMPLETED`.

---

## 5. Verification Results

- **Backend Unit & Regression Suite**:
  - Total tests: **187 passing**, 0 failing.
  - Test coverage: **86%** total codebase coverage (meets >= 85% requirement).
  - Dedicated Phase 3A test modules:
    - `test_adoption_listings.py`
    - `test_adoption_applications.py`
    - `test_adoption_review.py`
    - `test_adoption_privacy.py`
    - `test_adoption_concurrency.py`
    - `test_foster_matching.py`
    - `test_foster_assignments.py`
    - `test_foster_care_updates.py`
    - `test_foster_verification.py`
    - `test_foster_concurrency.py`
    - `test_foster_privacy.py`

- **Frontend Unit Suite**:
  - Total tests: **67 passing**, 0 failing across 14 test files.
  - Dedicated Phase 3A unit tests:
    - `FosterDashboard.test.tsx`
    - `AdoptionBrowse.test.tsx`
    - `AdoptionDetail.test.tsx`
    - `AdoptionApplicationPage.test.tsx`
    - `MyAdoptionApplications.test.tsx`
    - `NGOFoster.test.tsx`
    - `NGOAdoptions.test.tsx`

- **Frontend Production Build**:
  - `tsc -b && vite build`: Succeeded with **0 TypeScript errors** and clean bundle output.

- **Mocked UI Contract Suite (Playwright)**:
  - `foster-adoption-contract.spec.ts` + core contract suites: **9 passed, 0 failed**.

- **Unmocked Fullstack E2E Suite (Playwright)**:
  - `foster-adoption.spec.ts` testing end-to-end multi-actor flow:
    1. Deterministic foster matching and assignment offer dispatch by NGO.
    2. Foster caregiver login, placement acceptance, and daily care log submission.
    3. Public catalog browsing, detailed profile viewing, and citizen adoption application.
    4. NGO visit scheduling, cross-user authorization enforcement, and transactional approval cascade.
    5. Database verification of `ADOPTED` case status, `CLOSED` listing status, and public catalog omission.
