# PawReach Phase 3B — Hybrid AI-Assisted Visual Triage, Auditability & Safety

## 1. Executive Summary

Phase 3B introduces **Hybrid AI-Assisted Visual Triage** to PawReach. The system provides decision-support capabilities for emergency rescue prioritization by augmenting deterministic rule-based intake with asynchronous visual intelligence.

Critically, this capability operates under strict safety and regulatory guardrails:
1. **Decision Support Only**: Visual triage evaluates urgency to expedite dispatch; it does **not** diagnose medical conditions, classify veterinary injuries, or prescribe treatment.
2. **Non-Downgrade Safety Invariant**: The Hybrid Fusion Engine can only **maintain or escalate** priority. It can **never** downgrade a case. Hard emergency rules (e.g. CRITICAL for unconsciousness) remain invariant.
3. **Zero Dispatch Latency**: Visual assessment executes asynchronously in a background Celery worker (`ai_triage` queue). Case creation and initial dispatch are never blocked.
4. **Render Free-Tier Compliance**: No heavyweight deep learning models (PyTorch, TensorFlow, YOLO) run on the memory-constrained 512MB RAM free-tier instances. The architecture is provider-neutral, defaulting to `disabled`.

---

## 2. Architecture Overview

```text
Citizen / Reporter
       │
       ▼ (Submit Report + Photo)
FastAPI Backend ──(Sync)──► Evaluates Deterministic Rule Triage
       │                   Saves RescueCase (Priority set immediately)
       │                   Enqueues Async Celery Task
       ▼
Celery Worker (`ai_triage` queue)
       │
       ├──► Loads image bytes via StorageService.get_image_bytes() (bounded, PIL bomb-safe)
       ├──► Calls VisionTriageProvider (Factory selects disabled / mock / external)
       ├──► Feeds AI Output into HybridTriageFusionEngine
       │       ├── Non-downgrade check
       │       ├── Confidence gating (default: >= 0.70)
       │       └── Escalation logic
       ├──► Records auditable TriageAssessment in PostgreSQL
       └──► If Escalated:
               ├── Updates RescueCase priority, score, reasons
               ├── Logs RescueStatusHistory audit entry
               ├── Alerts NGO Admins if escalated to CRITICAL
               └── Calls DispatchService.handle_priority_escalation() (expands radius & offers)
```

---

## 3. Core Safety Rules & Invariants

### Rule 1: Non-Downgrade Invariant
The fusion policy enforces:
$$\text{Final Priority} = \max(\text{Rule Priority}, \text{AI Priority (if confidence} \ge \tau\text{)})$$

Where priority ordering is:
$$\text{CRITICAL} > \text{URGENT} > \text{MODERATE} > \text{GENERAL}$$

If the visual provider suggests a lower priority than the rule engine, the suggestion is ignored and the rule priority is preserved.

### Rule 2: Invariant Emergency Floor
If deterministic rules classify a case as `CRITICAL` (e.g. unconscious animal, vehicle collision with severe bleeding), no visual evaluation can alter that status downwards.

### Rule 3: Confidence Gating
An AI suggestion is only eligible to escalate priority if its confidence score meets or exceeds `AI_TRIAGE_MIN_CONFIDENCE` (default: `0.70`). Low-confidence evaluations are recorded in the audit trail but do not alter dispatch.

### Rule 4: Non-Diagnostic Language & Legal Disclaimer
Every triage response and UI view includes the mandatory legal disclaimer:
> *"AI visual triage provides decision-support for rescue dispatch urgency only. It does not constitute a veterinary medical diagnosis, injury assessment, or treatment prescription."*

---

## 4. Provider-Neutral Architecture

The AI subsystem is located in `backend/app/ai/`:

| Component | File | Purpose |
| :--- | :--- | :--- |
| `VisionTriageProvider` | `app/ai/base.py` | Abstract base class defining the provider contract (`assess(image_bytes, context)`). |
| `DisabledVisionTriageProvider` | `app/ai/disabled.py` | Safe no-op provider used when feature flag is disabled or unconfigured. |
| `MockVisionTriageProvider` | `app/ai/mock.py` | Deterministic, test-only provider for automated test suites. |
| Provider Factory | `app/ai/factory.py` | Factory that instantiates the active provider based on environment variables. **Enforces that mock provider cannot run in production or staging environments.** |
| `HybridTriageFusionEngine` | `app/ai/fusion.py` | Pure logic engine that fuses rule-based inputs and AI results with non-downgrade guarantees. |

### Configuration Variables (`backend/app/config.py`)

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `AI_TRIAGE_ENABLED` | `false` | Master feature flag for visual triage. |
| `AI_TRIAGE_PROVIDER` | `"disabled"` | Active provider (`disabled`, `mock`, `custom_vision`). |
| `AI_TRIAGE_MIN_CONFIDENCE` | `0.70` | Minimum confidence threshold for escalation eligibility. |
| `AI_TRIAGE_MODEL_NAME` | `"pawreach-vision-safety"` | Model identifier for audit provenance. |
| `AI_TRIAGE_MODEL_VERSION` | `"v1.0"` | Model version identifier for audit provenance. |

---

## 5. Database Schema & Audit Trail

The `TriageAssessment` model (`backend/app/models/triage_assessment.py`) provides full provenance:

- `id`: Unique UUID identifier.
- `rescue_case_id`: FK to `rescue_cases.id` (CASCADE).
- `animal_image_id`: FK to `animal_images.id` (SET NULL).
- `source`: Assessment origin (`RULES`, `IMAGE_AI`, `HYBRID`).
- `status`: Execution status (`PENDING`, `COMPLETED`, `FAILED`, `SKIPPED`).
- `suggested_priority`: Priority suggested by visual model (`CRITICAL`, `URGENT`, `MODERATE`, `GENERAL`).
- `score`: Numeric urgency score (0–100).
- `confidence`: Provider confidence level (0.00–1.00).
- `visible_signs`: JSON array of detected visual signs (e.g. `["Active bleeding detected", "Severe tissue trauma"]`).
- `explanation`: Human-readable justification of visual findings.
- `provider`: Provider identifier (`mock`, `disabled`, etc.).
- `model_name`: Provenance identifier.
- `model_version`: Model release version.
- `sanitized_error_code`: Error category if failed (`IMAGE_LOAD_ERROR`, `PROVIDER_ERROR`, etc.).
- `created_at` & `completed_at`: Execution timing benchmarks.
- `ix_triage_assessment_idempotency`: Index on `(rescue_case_id, model_name, model_version)` ensuring idempotent background processing.

---

## 6. API Endpoints

### 1. `GET /api/v1/rescues/{case_id}/triage`
- **Access**: Any user authorized to view the case (Citizen reporter, assigned Rescuer, admitting Vet, NGO Admin, Super Admin).
- **Response**: `TriageDetailResponse` containing:
  - `final_priority`, `final_score`, `final_reason`
  - `rule_assessment`: baseline priority, score, and reported condition factors.
  - `ai_assessment`: visual status, suggested priority, confidence, visible signs tags, model provenance.
  - `disclaimer`: legal non-diagnostic notice.
- **Privacy Guarantee**: Zero citizen PII, coordinates, or responder personal information is exposed in this endpoint.

### 2. `POST /api/v1/rescues/{case_id}/triage/retry`
- **Access**: `NGO_ADMIN` and `SUPER_ADMIN` only.
- **Parameters**: `force` (boolean query param, default `false`).
- **Behavior**: Re-enqueues `perform_ai_triage_task` to re-evaluate evidence image.

---

## 7. Frontend Integration

1. **`TriageAdvisoryCard` (`frontend/src/components/TriageAdvisoryCard.tsx`)**:
   - Displays combined final priority with color-coded badges.
   - Dual-column comparison: Rule-Based Urgency vs. Visual AI Advisory.
   - Tag chips for detected trauma indicators.
   - Integrated retry action for NGO administrators.
   - Prominent, unmissable non-diagnostic disclaimer notice.
2. **Citizen Case Tracking (`frontend/src/pages/CaseTracking.tsx`)**:
   - Embeds `TriageAdvisoryCard` providing real-time transparency into how the case was triaged.
3. **NGO Command Center (`frontend/src/pages/ngo/NGOCaseDetail.tsx`)**:
   - Embeds `TriageAdvisoryCard` with full administrative retry actions and audit details.
4. **Report Rescue Flow (`frontend/src/pages/ReportRescue.tsx`)**:
   - Explicit advisory notice in Step 2 (Photo Upload) and Step 4 (Condition Assessment) clarifying that visual intelligence assists dispatch urgency and does not replace licensed veterinary evaluation.

---

## 8. Free-Tier Operational Safety

To adhere strictly to Render free-tier constraints (512MB RAM, single-process Celery worker):
- **Worker Configuration**: Celery worker is spawned with concurrency limit 1 (`--concurrency=1`), bounded timeout (`--time-limit=45`), and tasks running on queue `ai_triage`.
- **Memory Safety**: `storage_service.get_image_bytes` bounds image payloads to 10MB and validates decompression dimensions to avoid memory spikes.
- **Fail-Safe Operation**: If Celery or Redis is congested, case creation and manual dispatch operate normally without degradation. AI triage failure is non-fatal and records an audit entry.
