# Staging Pilot Field Execution Guide: 5 Operational Scenarios
**PawReach MVP Phase 2.9 — Pilot Protocol**

This document defines the step-by-step protocol for conducting controlled field pilot trials in the PawReach staging environment across the 5 core emergency response scenarios.

---

## 1. Pilot Environment Preparation & Pre-Requisites

### Pre-Requisites
1. Staging deployment is running and healthy:
   ```bash
   python scripts/staging_smoke_test.py --api https://api.staging.pawreach.org --frontend https://staging.pawreach.org
   ```
2. Database initialized with Alembic and seeded with staging fixtures:
   ```bash
   cd backend
   alembic upgrade head
   STAGING_SEED_PASSWORD="<YourSecureStagingPassword14+!>" python scripts/seed_staging.py
   ```

### Staging Pilot Test Accounts
| Role | Email | Organization | Password |
| :--- | :--- | :--- | :--- |
| **Super Admin** | `superadmin@pawreach.org` | Global | `STAGING_SEED_PASSWORD` |
| **NGO Admin (Org A)** | `admin@strayrelief.org` | Stray Relief Foundation | `STAGING_SEED_PASSWORD` |
| **NGO Dispatcher (Org A)** | `dispatch@strayrelief.org` | Stray Relief Foundation | `STAGING_SEED_PASSWORD` |
| **Field Responder 1 (Org A)** | `responder1@strayrelief.org` | Stray Relief Foundation | `STAGING_SEED_PASSWORD` |
| **Field Responder 2 (Org A)** | `responder2@strayrelief.org` | Stray Relief Foundation | `STAGING_SEED_PASSWORD` |
| **Clinic Veterinarian** | `vet@southmumbaiclinic.org` | South Mumbai Veterinary Hospital | `STAGING_SEED_PASSWORD` |
| **NGO Admin (Org B - Isolated)** | `admin@animalaid.org` | Animal Aid Alliance | `STAGING_SEED_PASSWORD` |

---

## 2. Scenario 1: Citizen Emergency Reporting to NGO Dispatch

### Objective
Verify that a citizen can report an animal emergency from a mobile browser, that the report is accurately triaged, and that dispatch offers are generated for responders within the 5 km radius.

### Protocol Steps
1. **Citizen Access**: Open `https://staging.pawreach.org/report` on a mobile browser or desktop.
2. **Location Selection**: Allow GPS access or select location (e.g., Lat: `18.9220`, Lon: `72.8346`).
3. **Animal Details**:
   - Species: `DOG`
   - Condition: `SEVERE_INJURY` / Bleeding heavily, hit by vehicle
   - Urgency indicators: Check "Unconscious / Severe Trauma"
4. **Photo Attachment**: Attach camera photo of animal (simulated or real).
5. **Submission**: Click **Submit Emergency Rescue Report**.
6. **Confirmation**: Note the returned Case Public Tracking ID (e.g., `CASE-XXXX-XXXX`).

### Expected System Behavior & Validation
- Case is created with `status: PENDING_DISPATCH`.
- Triage score is calculated $\ge 70$, urgency marked `CRITICAL`.
- Dispatch Engine generates Wave 1 offers targeting active responders within 5 km.
- **NGO Dispatcher Verification**:
  - Log in as `admin@strayrelief.org` at `https://staging.pawreach.org/ngo/overview`.
  - Confirm new emergency case appears in the live operational queue.
  - Verify pin appears on Leaflet map at reported coordinates.

---

## 3. Scenario 2: Progressive Radius Escalation

### Objective
Verify that if responders in the initial wave do not accept the dispatch within the expiration window, the background engine automatically escalates through expanding radii (5 km $\to$ 10 km $\to$ 20 km $\to$ 40 km $\to$ `UNRESOLVED`).

### Protocol Steps
1. Create a `CRITICAL` emergency report using the steps in Scenario 1.
2. Ensure no field responders accept the incoming offer.
3. Observe background processing across expiration cycles (20 seconds per wave in staging configuration).
4. Monitor case dispatch state via API or NGO Command Center:
   ```bash
   curl -s -H "Authorization: Bearer <ADMIN_TOKEN>" \
     https://api.staging.pawreach.org/api/v1/cases/<CASE_ID>/dispatch-status
   ```

### Expected System Behavior & Validation
- **Wave 1 (0s - 20s)**: Radius 5 km. Offers dispatched.
- **Wave 2 (20s - 40s)**: Radius 10 km. Wave 1 offers marked `EXPIRED`. Wave 2 offers generated.
- **Wave 3 (40s - 60s)**: Radius 20 km. Wave 2 offers marked `EXPIRED`.
- **Wave 4 (60s - 80s)**: Radius 40 km. Wave 3 offers marked `EXPIRED`.
- **Exhaustion (80s+)**: If Wave 4 expires without acceptance, case transitions to `status: UNRESOLVED`.
- An escalation event is logged in `rescue_status_history` and a high-priority alert is delivered to the NGO Dispatcher console.

---

## 4. Scenario 3: Rescuer Acceptance & Transport Lifecycle

### Objective
Verify atomic dispatch acceptance (preventing race condition double-claims), status advancement, on-scene photo upload, and transport handoff.

### Protocol Steps
1. **Offer Receipt**:
   - Log in as `responder1@strayrelief.org` on device A.
   - Log in as `responder2@strayrelief.org` on device B.
   - Both receive dispatch offer for the same pending case.
2. **Concurrent Claim Test**:
   - Both responders click **Accept Offer** simultaneously.
3. **Atomic Claim Validation**:
   - Responder 1 receives confirmation: Case status updates to `ACCEPTED`, responder assigned.
   - Responder 2 receives conflict banner: `"Offer no longer available / claimed by another responder"` (HTTP 409 Conflict).
4. **Lifecycle Advancement**:
   - Responder 1 clicks **En Route to Animal** (`status: EN_ROUTE_TO_ANIMAL`).
   - Responder 1 arrives on scene, clicks **Arrived on Scene** (`status: ARRIVED_ON_SCENE`).
   - Responder 1 uploads on-scene photo evidence via `/api/v1/uploads/image`.
   - Responder 1 clicks **Transporting to Clinic** (`status: EN_ROUTE_TO_VET`), selecting South Mumbai Veterinary Hospital.

### Expected System Behavior & Validation
- Case status updates sequentially in database with audit timestamps.
- Arrival latency is accurately measured from `ACCEPTED` to `ARRIVED_ON_SCENE`.
- Uploaded photo is processed through WebP/Lanczos pipeline and stored in S3.
- NGO Overview live feed updates responder location and case state.

---

## 5. Scenario 4: Veterinary Clinical Intake & Treatment

### Objective
Verify clinic workflow: arrival confirmation, clinical examination, treatment plan recording, and patient outcome disposition.

### Protocol Steps
1. **Clinic Intake**:
   - Log in as `vet@southmumbaiclinic.org` at `https://staging.pawreach.org/vet`.
   - Locate incoming patient case in the **Incoming Transports** queue.
   - Click **Confirm Patient Arrival** (`status: ARRIVED_AT_VET`).
2. **Clinical Assessment**:
   - Enter triage diagnosis: `Right femoral fracture, moderate dehydration`.
   - Enter vital signs: Weight `14.5 kg`, Temp `38.8 C`, Heart Rate `110 bpm`.
   - Enter treatment plan: `Surgical stabilization, IV fluids, analgesia (meloxicam)`.
   - Save clinical intake record.
3. **Treatment Completion**:
   - Advance status to `IN_TREATMENT`.
   - After treatment progression, record discharge notes: `Fracture stabilized, weight-bearing, vaccinated`.
   - Advance status to `RECOVERED` or `DISCHARGED`.

### Expected System Behavior & Validation
- Clinical intake record persists in `veterinary_records` linked to the rescue case.
- Case status in NGO dashboard reflects `RECOVERED` or `DISCHARGED`.
- Response and treatment duration metrics update in NGO Analytics.

---

## 6. Scenario 5: Multi-Tenant Security & Organization Isolation

### Objective
Verify strict boundary defense between organizations: an admin from Organization A cannot access, query, or mutate records from Organization B.

### Protocol Steps
1. **Authorized Query**:
   - Log in as `admin@strayrelief.org` (Org ID: 1).
   - Fetch Org A responders: `GET /api/v1/ngo/responders`.
   - Confirm only Org A responders (`responder1`, `responder2`) are returned.
2. **Cross-Tenant Mutation Attempt**:
   - Attempt to modify responder status belonging to Org B (Org ID: 2, User ID: 7):
     ```bash
     curl -X PATCH -H "Authorization: Bearer <ORG_A_ADMIN_TOKEN>" \
       -H "Content-Type: application/json" \
       -d '{"status": "INACTIVE"}' \
       https://api.staging.pawreach.org/api/v1/ngo/responders/7/status
     ```
3. **Cross-Tenant Adoption Attempt**:
   - Attempt to reassign responder 7's organization to Org 1:
     ```bash
     curl -X PATCH -H "Authorization: Bearer <ORG_A_ADMIN_TOKEN>" \
       -H "Content-Type: application/json" \
       -d '{"organization_id": 1}' \
       https://api.staging.pawreach.org/api/v1/ngo/responders/7/status
     ```

### Expected System Behavior & Validation
- Mutation attempt is immediately rejected with HTTP 403 Forbidden (`CROSS_TENANT_RESPONDER_UPDATE_DENIED`).
- Adoption attempt is rejected: organization reassignment is restricted exclusively to `SUPER_ADMIN`.
- An immutable entry is written to `audit_logs` table recording:
  - `actor_id`: User ID of Org A Admin
  - `target_user_id`: 7
  - `target_org_id`: 2
  - `action`: `CROSS_TENANT_RESPONDER_UPDATE_DENIED`
  - `timestamp`: UTC timestamp of the violation.

---

## 7. Pilot Execution Summary & Sign-Off

Upon completing the 5 scenarios on the staging environment:
1. Record operational logs and latency metrics in `docs/PILOT_RESULTS.md`.
2. Inspect `audit_logs` table to confirm zero unlogged security exceptions.
3. Verify that all subsystems remain `ready` via `/api/v1/health/readiness`.
