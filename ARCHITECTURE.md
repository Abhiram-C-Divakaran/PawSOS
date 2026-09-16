# PawReach – System Architecture

> [!IMPORTANT]
> **Implementation Status**:
> - **Current Implemented Architecture**: React 19 / TypeScript / Vite PWA frontend + FastAPI Python 3.12 backend + PostgreSQL/PostGIS + Upstash Redis over TLS + Celery background worker + Supabase S3 private storage. Hosted on zero-cost free-tier cloud infrastructure (Render + Supabase + Upstash).
> - **Phase 3B AI Triage Architecture**: Lightweight decision-support visual urgency triage engine via provider-neutral interface (`backend/app/ai/`). Strictly non-diagnostic and fail-safe (hard-rule priorities can never be downgraded).
> - **Conceptual / Future Notes**: Historical references in this document to native Flutter apps, heavy local deep-learning frameworks (PyTorch/YOLO), or multi-container enterprise setups represent early conceptual planning and are not part of the active free-tier demo implementation.

## 1. Architecture Overview

PAWSOS follows a **layered client-server architecture**.

The main layers are:

1. Client Layer
2. API / Backend Layer
3. Business Logic Layer
4. AI Processing Layer
5. Data Layer
6. External Services Layer
7. Notification Layer
8. Administration and Analytics Layer

---

# 2. High-Level Architecture

```text
                     ┌──────────────────────────────┐
                     │          USERS               │
                     │                              │
                     │ Citizen | Volunteer | Vet    │
                     │ NGO | Foster | Admin         │
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │       FRONTEND LAYER         │
                     │                              │
                     │ Flutter Mobile Application   │
                     │ React Admin/Vet Dashboard    │
                     └──────────────┬───────────────┘
                                    │
                                  HTTPS
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │       FASTAPI BACKEND        │
                     │                              │
                     │ Authentication               │
                     │ Rescue Management            │
                     │ Animal Management            │
                     │ Volunteer Matching           │
                     │ Vet/Foster Management        │
                     │ Notification Handling        │
                     └──────┬────────┬────────┬─────┘
                            │        │        │
                ┌───────────┘        │        └────────────┐
                ▼                    ▼                     ▼
       ┌────────────────┐   ┌─────────────────┐   ┌────────────────┐
       │   AI SERVICE   │   │   POSTGRESQL    │   │ MAP SERVICES   │
       │                │   │   + PostGIS     │   │                │
       │ PyTorch        │   │                 │   │ Google Maps /  │
       │ YOLO           │   │ Users           │   │ OpenStreetMap  │
       │ OpenCV         │   │ Animals         │   │                │
       └────────────────┘   │ Rescue Cases    │   └────────────────┘
                            │ Treatments      │
                            │ Locations       │
                            └────────┬────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │ CLOUD SERVICES  │
                            │                 │
                            │ Cloudinary      │
                            │ Firebase FCM    │
                            │ Redis           │
                            └─────────────────┘
```

---

# 3. Client Layer

The client layer contains the interfaces used by all users.

## 3.1 Citizen Mobile Application

Technology:
```text
Flutter + Dart
```

Citizens can:
* Register and login
* Take/upload animal photos
* Share GPS location
* Report an injured animal
* Answer emergency questions
* Track rescue status
* Receive notifications
* Add additional sightings
* View previous reports

---

## 3.2 Volunteer / Rescuer Application

The same Flutter application can provide a different interface based on user role.

Rescuers can:
* Set themselves as available/unavailable
* Receive nearby rescue requests
* Accept/reject assignments
* View animal location
* Navigate to rescue location
* Update rescue status
* Upload rescue photos
* Select veterinary hospital
* Complete rescue handover

---

## 3.3 Veterinary Dashboard

Technology:
```text
React.js
```

Veterinarians can:
* View incoming rescued animals
* Update health information
* Add diagnosis
* Add treatment
* Update vaccination details
* Update sterilization details
* Add medicines
* Set recovery status
* Mark animal ready for discharge

---

## 3.4 Administrator Dashboard

Technology:
```text
React.js
```

Administrators can:
* Manage users
* Verify volunteers
* Verify NGOs
* Verify veterinary facilities
* View all rescue cases
* Manually assign responders
* Monitor critical cases
* View rescue heatmaps
* Detect fraudulent reports
* View analytics

---

# 4. Backend Layer

Technology:
```text
Python
FastAPI
```

The backend acts as the central controller of PAWSOS.

Example API flow:
```text
Flutter App
      │
      │ REST API
      ▼
FastAPI Backend
      │
      ├── Authentication
      ├── Rescue Cases
      ├── Animals
      ├── Volunteers
      ├── Veterinary Records
      ├── Foster Management
      ├── Notifications
      └── AI Integration
```

---

# 5. Backend Modules

## 5.1 Authentication Service

Responsible for:
* Registration
* Login
* Password management
* JWT generation
* Role-based access control
* Account verification

Roles:
```text
Citizen
Volunteer
NGO
Veterinarian
Foster Caregiver
Administrator
```

---

# 6. Rescue Management Service

This is the core module.
It manages the complete rescue lifecycle.

```text
Reported
   ↓
Triaged
   ↓
Responder Search
   ↓
Assigned
   ↓
Rescuer En Route
   ↓
Animal Located
   ↓
Rescued
   ↓
Transporting
   ↓
Under Treatment
   ↓
Recovering
   ↓
Foster / Release / Adoption
   ↓
Closed
```

Each status change is stored in the database.

---

# 7. Animal Reporting Architecture

When a citizen reports an animal:
```text
Citizen
   ↓
Take Photo
   ↓
Capture GPS
   ↓
Answer Emergency Questions
   ↓
Submit
```

The Flutter application sends:
```json
{
  "animal_type": "dog",
  "latitude": "...",
  "longitude": "...",
  "description": "...",
  "bleeding": true,
  "can_walk": false,
  "accident": true,
  "image_url": "..."
}
```
to the FastAPI backend.

The backend creates:
```text
Rescue Case
+
Case ID
+
Timestamp
+
Initial Status
```

---

# 8. Image Storage Architecture

Images should not be stored directly inside PostgreSQL.

Architecture:
```text
Flutter
   ↓
Image Upload
   ↓
Cloudinary / S3
   ↓
Image URL
   ↓
FastAPI
   ↓
PostgreSQL
```

The database stores only:
```text
image_id
case_id
image_url
uploaded_at
```

---

# 9. AI Architecture

Technology:
```text
Python
PyTorch
YOLO
OpenCV
```

AI should work as a separate logical module.

```text
Uploaded Image
      ↓
OpenCV Preprocessing
      ↓
YOLO Animal Detection
      ↓
Animal Region Extraction
      ↓
AI Classification
      ↓
Emergency Questionnaire
      ↓
Rule-Based System
      ↓
Final Priority Score
```

---

# 10. AI Emergency Triage

The AI should not make a veterinary diagnosis.
Its purpose is only to help determine urgency.

Inputs:
```text
Image
Animal Type
Bleeding
Mobility
Consciousness
Accident Information
User Description
```

Output:
```text
Emergency Score
+
Priority Category
+
Confidence
```

Example:
```text
Emergency Score: 88/100

Priority:
CRITICAL

Reasons:
- Visible bleeding
- Animal unable to walk
- Road accident reported
```

---

# 11. Hybrid Decision Architecture

Do not depend entirely on AI.

Use:
```text
AI Prediction
      +
Rule-Based Logic
      +
Citizen Questionnaire
      ↓
Final Priority
```

Example rule:
```text
IF heavy_bleeding = TRUE
AND can_walk = FALSE

THEN
priority = CRITICAL
```

---

# 12. Priority Levels

Recommended categories:
* **Priority 1 (CRITICAL)**: Immediate rescue required
* **Priority 2 (URGENT)**: Rescue required soon
* **Priority 3 (MODERATE)**: Medical attention required
* **Priority 4 (GENERAL)**: Non-emergency welfare issue

---

# 13. Duplicate Report Detection Architecture

Several citizens may report the same animal.
The backend checks:
* Location
* Time
* Animal Type
* Image Similarity

Possible result: `Likely Duplicate`. Linked to existing rescue case.

---

# 14. Volunteer Matching Architecture

When a rescue case receives a priority:
```text
Rescue Case -> Location -> PostGIS Search -> Nearby Volunteers -> Filter Available -> Calculate Score -> Dispatch Request
```

---

# 15. Geographic Search

Use PostgreSQL + PostGIS (e.g., within 5 km radius).

---

# 16. Volunteer Matching Algorithm

```text
Responder Score = 
    40% Distance + 
    25% Availability + 
    15% Experience + 
    10% Vehicle Availability + 
    10% Reliability
```

---

# 17. Dispatch Architecture

Critical rescue dispatches sequentially or concurrently to highest match responders, with fallback escalation to NGOs/Admins.

---

# 18. Maps Architecture

Google Maps API / OpenStreetMap for navigation, routing, hospitals, and heatmaps.

---

# 19. Veterinary Architecture

Rescuer brings animal to vet hospital. Veterinarian logs diagnosis, treatments, vaccinations, sterilization, follow-ups, and recovery status.

---

# 20. Animal Digital Profile

Unique ID (e.g. `PAW-KL-DOG-000238`) containing medical, rescue, and foster records.

---

# 21. Foster Architecture

Post-treatment recovery matching considering species, size, capacity, and recovery needs.

---

# 22. Notification Architecture

Firebase Cloud Messaging (FCM) for real-time dispatch alerts and case status updates.

---

# 23. Database Architecture

PostgreSQL + PostGIS schema:
- `users`, `roles`
- `animals`
- `rescue_cases`, `case_status_history`, `rescue_images`
- `volunteers`, `rescue_assignments`
- `veterinary_hospitals`, `treatments`
- `foster_homes`, `foster_assignments`
- `notifications`

---

# 24. Redis Architecture (Optional / Phase 2)

Online status, ephemeral volunteer locations, rate limiting, and queues.

---

# 25. Security Architecture

- JWT Authentication & Argon2 / bcrypt password hashing
- Role-Based Access Control (RBAC)
- Location data privacy and audit logging

---

# 26. Analytics & Heatmaps

Rescue density heatmaps, response time tracking, recovery rates, and reporting.

---

# 27. Recommended MVP Architecture

Modular Monolith with FastAPI:
```text
app/
├── auth/
├── users/
├── animals/
├── rescues/
├── volunteers/
├── vets/
├── notifications/
├── maps/
├── ai/
└── analytics/
```
