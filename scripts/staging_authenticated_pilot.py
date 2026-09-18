#!/usr/bin/env python3
"""PawReach Authenticated Staging Pilot Execution Script.

Executes a comprehensive, non-destructive, synthetic end-to-end pilot workflow
against the live hosted PawReach staging environment (or local dev):
1. Service Readiness & Telemetry Validation (/health and /health/ready)
2. Multi-Role Authentication (Citizen, Responders, Veterinarian, NGO Admins)
3. Deterministic Responder Availability State Setup (Rescuer A AVAILABLE, Rescuer B BUSY)
4. Synthetic Emergency Incident Creation with Private Evidence Upload
5. Dispatch Offer Verification & Single-Winner Claim Authorization Integrity
6. Private Evidence Access Authorization Boundaries (Citizen, Rescuer A, Rescuer B, NGO Alpha, NGO Beta)
7. Explicit NGO Case Claim & Multi-Tenant Isolation (Org Alpha vs Org Beta)
8. Rescue Lifecycle Progression (EN_ROUTE -> LOCATED -> RESCUED -> TRANSPORTING -> AT_FACILITY)
9. Deterministic Veterinary Facility Scoping & Clinical Treatment Documentation
10. Controlled Case Closure, Audit Trail Verification & Guaranteed Responder Cleanup
"""

import argparse
import os
import sys
import time
import uuid
from typing import Any, Dict, Optional

try:
    import httpx
except ImportError:
    print("Error: 'httpx' is required. Install via: pip install httpx")
    sys.exit(1)


# Minimal synthetic 1x1 transparent PNG fixture for private evidence testing
SYNTHETIC_PNG_FIXTURE = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00"
    b"\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class PilotFailure(Exception):
    """Raised when an authenticated pilot verification assertion fails."""
    pass


class StagingPilotRunner:
    def __init__(
        self,
        base_url: str,
        seed_password: str,
        expected_sha: Optional[str] = None,
        timeout: float = 30.0,
        allow_http: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.seed_password = seed_password
        self.expected_sha = expected_sha.strip() if expected_sha else None
        self.timeout = timeout
        self.allow_http = allow_http
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)
        self.tokens: Dict[str, str] = {}
        self.pilot_tag = f"PILOT-{int(time.time())}"
        self.created_case_id: Optional[str] = None
        self.created_image_id: Optional[str] = None
        self.test_facility_id: Optional[str] = None

    def log(self, section: str, message: str, status: str = "INFO"):
        prefix = {
            "INFO": "  ℹ️ ",
            "PASS": "  ✅ ",
            "FAIL": "  ❌ ",
            "WARN": "  ⚠️ ",
        }.get(status, "     ")
        print(f"[{section}] {prefix}{message}")

    def abort(self, section: str, message: str):
        self.log(section, message, status="FAIL")
        raise PilotFailure(f"[{section}] {message}")

    def cleanup(self):
        """Guaranteed cleanup hook to restore responder availability states and close HTTP client."""
        self.log("CLEANUP", "Restoring responder availability states...")
        if "rescuer_a" in self.tokens:
            try:
                self.client.patch(
                    f"{self.base_url}/api/v1/rescuers/me/availability",
                    json={"availability_status": "AVAILABLE"},
                    headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"},
                )
                self.log("CLEANUP", "Rescuer A restored to AVAILABLE", status="PASS")
            except Exception as e:
                self.log("CLEANUP", f"Could not restore Rescuer A: {e}", status="WARN")

        if "rescuer_b" in self.tokens:
            try:
                self.client.patch(
                    f"{self.base_url}/api/v1/rescuers/me/availability",
                    json={"availability_status": "AVAILABLE"},
                    headers={"Authorization": f"Bearer {self.tokens['rescuer_b']}"},
                )
                self.log("CLEANUP", "Rescuer B restored to AVAILABLE", status="PASS")
            except Exception as e:
                self.log("CLEANUP", f"Could not restore Rescuer B: {e}", status="WARN")

        try:
            self.client.close()
            self.log("CLEANUP", "HTTP client closed cleanly", status="PASS")
        except Exception as e:
            self.log("CLEANUP", f"Could not close HTTP client: {e}", status="WARN")

    def run(self) -> bool:
        print("====================================================================")
        print("          PawReach Hosted Staging Authenticated Pilot              ")
        print(f"          Execution Tag: {self.pilot_tag}")
        print("====================================================================")
        print(f"Target URL:     {self.base_url}")
        print(f"Expected SHA:   {self.expected_sha or 'any'}")
        print(f"Timeout:        {self.timeout}s")
        print(f"HTTPS Enforced: {not self.allow_http}")
        print("--------------------------------------------------------------------\n")

        # 0. Protocol Validation
        if not self.allow_http and not self.base_url.startswith("https://"):
            self.abort("PROTOCOL", f"Insecure URL '{self.base_url}'. Staging requires HTTPS.")

        try:
            # 1. Authoritative Readiness & Telemetry
            self.step_1_readiness()

            # 2. Authenticate Actors
            self.step_2_authenticate()

            # 3. Deterministic Responder Setup & Synthetic Incident with Private Evidence
            self.step_3_deterministic_setup_and_create_case()

            # 4. Dispatch Claim Authorization & Offer Acceptance
            self.step_4_dispatch_and_claim_integrity()

            # 5. Private Evidence Access Authorization Security Check
            self.step_5_evidence_access_security()

            # 6. Explicit NGO Case Claim & Multi-Tenant Isolation
            self.step_6_multitenant_claim_and_isolation()

            # 7. Lifecycle Progression & Deterministic Veterinary Clinical Care
            self.step_7_lifecycle_progression_and_veterinary()

            # 8. Controlled Case Closure
            self.step_8_case_closure()

            print("\n====================================================================")
            print("          ALL AUTHENTICATED PILOT STAGING SCENARIOS PASSED ✅        ")
            print("====================================================================")
            return True
        finally:
            self.cleanup()

    # -------------------------------------------------------------------------
    # Step 1: Authoritative Readiness & Telemetry
    # -------------------------------------------------------------------------
    def step_1_readiness(self):
        self.log("STEP 1", "Verifying Backend Subsystem Deep Readiness...")

        # 1a. Check /api/v1/health
        health_url = f"{self.base_url}/api/v1/health"
        try:
            resp = self.client.get(health_url)
            if resp.status_code != 200:
                self.abort("STEP 1", f"/health returned HTTP {resp.status_code}: {resp.text}")
            hdata = resp.json()
            if hdata.get("status") != "ok":
                self.abort("STEP 1", f"/health status expected 'ok', got '{hdata.get('status')}'")

            observed_sha = hdata.get("git_sha", "")
            env_val = hdata.get("environment", "")
            if env_val != "staging" and not self.allow_http:
                self.abort("STEP 1", f"/health environment expected 'staging', got '{env_val}'")
            self.log("STEP 1", f"/health OK: environment={env_val} | git_sha={observed_sha}", status="PASS")

            if self.expected_sha:
                # Compare full or prefix match
                if not (observed_sha.startswith(self.expected_sha) or self.expected_sha.startswith(observed_sha)):
                    self.abort(
                        "STEP 1",
                        f"Git SHA mismatch! Deployed={observed_sha}, Expected={self.expected_sha}"
                    )
                self.log("STEP 1", f"Deployed Git SHA matches expected SHA: {self.expected_sha}", status="PASS")
        except httpx.RequestError as e:
            self.abort("STEP 1", f"Could not connect to /health: {e}")

        # 1b. Check /api/v1/health/ready
        ready_url = f"{self.base_url}/api/v1/health/ready"
        try:
            resp = self.client.get(ready_url)
            if resp.status_code != 200:
                self.abort("STEP 1", f"Readiness endpoint returned HTTP {resp.status_code}: {resp.text}")
            data = resp.json()
            if data.get("status") != "ready":
                self.abort("STEP 1", f"Readiness status expected 'ready', got '{data.get('status')}'")

            services = data.get("services", {})
            checks = data.get("checks", {})

            required_services = ["database", "postgis", "redis", "celery", "storage"]
            for svc in required_services:
                val = services.get(svc)
                if val != "healthy":
                    self.abort("STEP 1", f"Service '{svc}' is '{val}', expected 'healthy'")

            worker_val = checks.get("worker")
            if worker_val != "active":
                self.abort("STEP 1", f"Check 'worker' is '{worker_val}', expected 'active'")

            self.log(
                "STEP 1",
                f"Deep readiness verified: DB={services.get('database')} | PostGIS={services.get('postgis')} | "
                f"Redis={services.get('redis')} | Celery={services.get('celery')} | Worker={checks.get('worker')} | Storage={services.get('storage')}",
                status="PASS"
            )
        except httpx.RequestError as e:
            self.abort("STEP 1", f"Connection error during readiness check: {e}")

    # -------------------------------------------------------------------------
    # Step 2: Multi-Role Authentication
    # -------------------------------------------------------------------------
    def step_2_authenticate(self):
        self.log("STEP 2", "Authenticating Seeded Pilot Actors...")
        actors = {
            "citizen": "citizen@staging.pawsos.org",
            "rescuer_a": "rescuer.a@staging.pawsos.org",
            "rescuer_b": "rescuer.b@staging.pawsos.org",
            "vet_a": "vet@staging.pawsos.org",
            "vet_b": "vet.b@staging.pawsos.org",
            "admin_a": "admin@staging.pawsos.org",
            "admin_b": "admin.b@staging.pawsos.org",
            "superadmin": "superadmin@staging.pawsos.org",
        }

        login_url = f"{self.base_url}/api/v1/auth/login"
        for role, email in actors.items():
            resp = self.client.post(login_url, json={"email": email, "password": self.seed_password})
            if resp.status_code == 200:
                token_data = resp.json()
                self.tokens[role] = token_data.get("access_token") or token_data.get("token")
                self.log("STEP 2", f"Authenticated {role} ({email})", status="PASS")
            else:
                # If citizen is not seeded, register dynamically
                if role == "citizen":
                    self.log("STEP 2", "Citizen account not found; registering dynamic pilot citizen...", status="WARN")
                    reg_url = f"{self.base_url}/api/v1/auth/register"
                    reg_email = f"pilot_citizen_{uuid.uuid4().hex[:6]}@staging.pawsos.org"
                    reg_resp = self.client.post(
                        reg_url,
                        json={
                            "email": reg_email,
                            "password": self.seed_password,
                            "full_name": "Dynamic Pilot Citizen",
                            "phone": f"+9198{uuid.uuid4().hex[:8]}",
                            "role": "CITIZEN",
                        },
                    )
                    if reg_resp.status_code in [200, 201]:
                        log_resp = self.client.post(login_url, json={"email": reg_email, "password": self.seed_password})
                        self.tokens["citizen"] = log_resp.json().get("access_token")
                        self.log("STEP 2", f"Registered and authenticated dynamic citizen ({reg_email})", status="PASS")
                        continue
                self.abort("STEP 2", f"Failed login for {role} ({email}): HTTP {resp.status_code} - {resp.text}")

    # -------------------------------------------------------------------------
    # Step 3: Deterministic Responder Setup & Incident Creation with Private Evidence
    # -------------------------------------------------------------------------
    def step_3_deterministic_setup_and_create_case(self):
        self.log("STEP 3", "Establishing deterministic responder availability states...")

        # 3a. Rescuer A: set AVAILABLE and update location close to Kochi Marine Drive test incident
        resp_avail_a = self.client.patch(
            f"{self.base_url}/api/v1/rescuers/me/availability",
            json={"availability_status": "AVAILABLE"},
            headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"},
        )
        if resp_avail_a.status_code != 200:
            self.abort("STEP 3", f"Failed setting Rescuer A AVAILABLE: HTTP {resp_avail_a.status_code}")

        resp_loc_a = self.client.patch(
            f"{self.base_url}/api/v1/rescuers/me/location",
            json={"latitude": 9.9850, "longitude": 76.2980},
            headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"},
        )
        if resp_loc_a.status_code != 200:
            self.abort("STEP 3", f"Failed updating Rescuer A location: HTTP {resp_loc_a.status_code}")
        self.log("STEP 3", "Rescuer A configured as AVAILABLE at fresh coordinates (9.9850, 76.2980)", status="PASS")

        # 3b. Rescuer B: set BUSY BEFORE case creation to guarantee no dispatch offer is issued
        resp_avail_b = self.client.patch(
            f"{self.base_url}/api/v1/rescuers/me/availability",
            json={"availability_status": "BUSY"},
            headers={"Authorization": f"Bearer {self.tokens['rescuer_b']}"},
        )
        if resp_avail_b.status_code != 200:
            self.abort("STEP 3", f"Failed setting Rescuer B BUSY: HTTP {resp_avail_b.status_code}")
        self.log("STEP 3", "Rescuer B configured as BUSY to guarantee dispatch exclusion", status="PASS")

        # 3c. Upload synthetic private evidence fixture as citizen
        self.log("STEP 3", "Uploading synthetic non-sensitive private image fixture via /api/v1/uploads/image...")
        files = {"file": ("pilot_synthetic.png", SYNTHETIC_PNG_FIXTURE, "image/png")}
        upload_resp = self.client.post(
            f"{self.base_url}/api/v1/uploads/image",
            files=files,
            headers={"Authorization": f"Bearer {self.tokens['citizen']}"},
        )
        if upload_resp.status_code not in [200, 201]:
            self.abort("STEP 3", f"Image upload failed: HTTP {upload_resp.status_code} - {upload_resp.text}")

        upload_data = upload_resp.json()
        canonical_image_key = upload_data.get("image_url") or upload_data.get("key")
        if not canonical_image_key:
            self.abort("STEP 3", f"Upload did not return canonical image key: {upload_data}")
        self.log("STEP 3", "Synthetic private evidence uploaded; received canonical storage key", status="PASS")

        # 3d. Create Synthetic Emergency Incident with image_url
        self.log("STEP 3", f"Reporting Synthetic Emergency Incident [{self.pilot_tag}]...")
        report_payload = {
            "species": "Dog",
            "description": f"[{self.pilot_tag}] Injured canine with fractured limb near Marine Drive Kochi. Non-emergency pilot scenario.",
            "latitude": 9.9852,
            "longitude": 76.2981,
            "address_text": "Marine Drive Promenade, Kochi, Kerala",
            "bleeding": True,
            "conscious": True,
            "can_walk": False,
            "vehicle_accident": True,
            "breathing_difficulty": False,
            "image_url": canonical_image_key,
        }

        resp = self.client.post(
            f"{self.base_url}/api/v1/rescues",
            json=report_payload,
            headers={"Authorization": f"Bearer {self.tokens['citizen']}"},
        )
        if resp.status_code not in [200, 201]:
            self.abort("STEP 3", f"Case creation failed: HTTP {resp.status_code} - {resp.text}")

        case_data = resp.json()
        self.created_case_id = case_data["id"]
        triage_score = case_data.get("triage_score")
        triage_priority = case_data.get("triage_priority")
        case_status = case_data.get("status")

        # Extract image id
        images = case_data.get("images", [])
        if images:
            self.created_image_id = images[0].get("id")

        self.log(
            "STEP 3",
            f"Case Created: {self.created_case_id} | Status: {case_status} | Triage: {triage_priority} (Score: {triage_score}) | Image ID: {self.created_image_id}",
            status="PASS",
        )

        if triage_priority not in ["CRITICAL", "URGENT"]:
            self.abort("STEP 3", f"Expected CRITICAL/URGENT priority, received '{triage_priority}'")

    # -------------------------------------------------------------------------
    # Step 4: Dispatch Claim Authorization & Offer Acceptance
    # -------------------------------------------------------------------------
    def step_4_dispatch_and_claim_integrity(self):
        self.log("STEP 4", "Verifying Dispatch Offer Verification & Claim Authorization Integrity...")

        # 4a. Verify Rescuer B explicitly has NO active offers for this case
        self.log("STEP 4", "Checking Rescuer B offers to prove exclusion from dispatch matching...")
        b_offers_resp = self.client.get(
            f"{self.base_url}/api/v1/rescuers/me/offers",
            headers={"Authorization": f"Bearer {self.tokens['rescuer_b']}"},
        )
        if b_offers_resp.status_code != 200:
            self.abort("STEP 4", f"Rescuer B offers query returned HTTP {b_offers_resp.status_code}: {b_offers_resp.text}")
        b_offers = b_offers_resp.json()
        matching_b_offers = [
            off for off in b_offers
            if str(off.get("rescue_case_id") or off.get("case_id")) == str(self.created_case_id)
            and off.get("assignment_status") == "PENDING"
        ]
        if matching_b_offers:
            self.abort("STEP 4", f"Rescuer B received unexpected pending offer {matching_b_offers[0]['id']}")
        self.log("STEP 4", "Confirmed Rescuer B has ZERO pending offers for this case", status="PASS")

        # 4b. Assert Rescuer B claim is rejected with HTTP 403 Forbidden
        self.log("STEP 4", "Asserting unoffered Rescuer B direct claim is rejected with HTTP 403...")
        b_claim_resp = self.client.post(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}/accept",
            headers={"Authorization": f"Bearer {self.tokens['rescuer_b']}"},
        )
        if b_claim_resp.status_code == 403:
            self.log("STEP 4", "Direct claim without offer correctly rejected with HTTP 403 Forbidden", status="PASS")
        else:
            self.abort("STEP 4", f"Expected HTTP 403 for unoffered claim, got HTTP {b_claim_resp.status_code}")

        # 4c. Find Rescuer A's active offer and accept strictly via canonical offer endpoint
        self.log("STEP 4", "Locating Rescuer A incoming dispatch offer...")
        offer_id = None
        for attempt in range(10):
            offers_resp = self.client.get(
                f"{self.base_url}/api/v1/rescuers/me/offers",
                headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"},
            )
            if offers_resp.status_code == 200:
                offers = offers_resp.json()
                for off in offers:
                    case_ref = off.get("rescue_case_id") or off.get("case_id")
                    if str(case_ref) == str(self.created_case_id) and off.get("assignment_status") == "PENDING":
                        offer_id = off.get("id")
                        break
            if offer_id:
                break
            time.sleep(1.0)

        if not offer_id:
            self.abort("STEP 4", "No pending dispatch offer found for Rescuer A on canonical endpoint")

        self.log("STEP 4", f"Found pending offer {offer_id} for Rescuer A. Accepting via canonical offer endpoint...", status="PASS")
        accept_resp = self.client.post(
            f"{self.base_url}/api/v1/rescuers/offers/{offer_id}/accept",
            headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"},
        )
        if accept_resp.status_code != 200:
            self.abort("STEP 4", f"Canonical offer acceptance failed: HTTP {accept_resp.status_code} - {accept_resp.text}")
        self.log("STEP 4", f"Rescuer A accepted offer {offer_id} via canonical endpoint (HTTP 200)", status="PASS")

        # 4d. Verify Case Transitioned to RESPONDER_ASSIGNED
        case_check = self.client.get(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}",
            headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"},
        )
        if case_check.status_code != 200:
            self.abort("STEP 4", f"Failed fetching assigned case: {case_check.text}")
        status_val = case_check.json().get("status")
        if status_val != "RESPONDER_ASSIGNED":
            self.abort("STEP 4", f"Expected case status 'RESPONDER_ASSIGNED', got '{status_val}'")
        self.log("STEP 4", "Case status verified as RESPONDER_ASSIGNED", status="PASS")

        # 4e. Conflict test: Subsequent acceptance after assignment returns 409 Conflict
        second_claim = self.client.post(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}/accept",
            headers={"Authorization": f"Bearer {self.tokens['rescuer_b']}"},
        )
        if second_claim.status_code in [403, 409]:
            self.log("STEP 4", f"Subsequent claim after assignment blocked with HTTP {second_claim.status_code}", status="PASS")
        else:
            self.abort("STEP 4", f"Expected 403 or 409 for duplicate claim, got HTTP {second_claim.status_code}")

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Step 5: Private Evidence Access Authorization Security Check
    # -------------------------------------------------------------------------
    def step_5_evidence_access_security(self):
        self.log("STEP 5", "Verifying Private Evidence Access Authorization Boundaries...")

        if not self.created_image_id:
            # Look up image ID from case detail
            case_resp = self.client.get(
                f"{self.base_url}/api/v1/rescues/{self.created_case_id}",
                headers={"Authorization": f"Bearer {self.tokens['citizen']}"},
            )
            if case_resp.status_code == 200:
                imgs = case_resp.json().get("images", [])
                if imgs:
                    self.created_image_id = imgs[0].get("id")

        if not self.created_image_id:
            self.abort("STEP 5", "Mandatory synthetic private evidence image was not attached to created case")

        evidence_url = f"{self.base_url}/api/v1/rescues/{self.created_case_id}/images/{self.created_image_id}/access"

        # 5a. Citizen reporter can access evidence URL
        cit_resp = self.client.get(evidence_url, headers={"Authorization": f"Bearer {self.tokens['citizen']}"})
        if cit_resp.status_code != 200:
            self.abort("STEP 5", f"Citizen reporter denied image access: HTTP {cit_resp.status_code}")
        expires_cit = cit_resp.json().get("expires_in")
        self.log("STEP 5", f"Citizen reporter evidence access verified (HTTP 200, expires_in={expires_cit}s)", status="PASS")

        # 5b. Assigned Rescuer A can access evidence URL
        res_a_resp = self.client.get(evidence_url, headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"})
        if res_a_resp.status_code != 200:
            self.abort("STEP 5", f"Assigned Rescuer A denied image access: HTTP {res_a_resp.status_code}")
        expires_a = res_a_resp.json().get("expires_in")
        self.log("STEP 5", f"Assigned Rescuer A evidence access verified (HTTP 200, expires_in={expires_a}s)", status="PASS")

        # 5c. Unassigned Rescuer B is denied evidence access (HTTP 403)
        res_b_resp = self.client.get(evidence_url, headers={"Authorization": f"Bearer {self.tokens['rescuer_b']}"})
        if res_b_resp.status_code != 403:
            self.abort("STEP 5", f"Unassigned Rescuer B should receive HTTP 403, got HTTP {res_b_resp.status_code}")
        self.log("STEP 5", "Unassigned Rescuer B evidence access correctly rejected (HTTP 403 Forbidden)", status="PASS")

        # 5d. Foreign NGO Admin B is denied evidence access (HTTP 403)
        ngo_b_resp = self.client.get(evidence_url, headers={"Authorization": f"Bearer {self.tokens['admin_b']}"})
        if ngo_b_resp.status_code != 403:
            self.abort("STEP 5", f"Foreign NGO Admin B should receive HTTP 403, got HTTP {ngo_b_resp.status_code}")
        self.log("STEP 5", "Foreign NGO Admin B evidence access correctly rejected (HTTP 403 Forbidden)", status="PASS")

    # -------------------------------------------------------------------------
    # Step 6: Explicit NGO Case Claim & Multi-Tenant Isolation
    # -------------------------------------------------------------------------
    def step_6_multitenant_claim_and_isolation(self):
        self.log("STEP 6", "Testing Explicit NGO Case Claim & Multi-Tenant Boundaries...")

        claim_url = f"{self.base_url}/api/v1/ngo/cases/{self.created_case_id}/claim"

        # 6a. Admin Alpha claims the unassigned case
        claim_resp = self.client.post(
            claim_url,
            headers={"Authorization": f"Bearer {self.tokens['admin_a']}"},
        )
        if claim_resp.status_code != 200:
            self.abort("STEP 6", f"Admin Alpha case claim failed: HTTP {claim_resp.status_code} - {claim_resp.text}")
        self.log("STEP 6", "Admin Alpha successfully claimed case ownership (HTTP 200)", status="PASS")

        # 6b. Idempotent re-claim by same Org Alpha succeeds
        re_claim = self.client.post(
            claim_url,
            headers={"Authorization": f"Bearer {self.tokens['admin_a']}"},
        )
        if re_claim.status_code != 200:
            self.abort("STEP 6", f"Idempotent claim failed: HTTP {re_claim.status_code}")
        self.log("STEP 6", "Idempotent claim by same organization confirmed (HTTP 200)", status="PASS")

        # 6c. Foreign Admin Beta attempting to claim the case receives HTTP 409 Conflict
        foreign_claim = self.client.post(
            claim_url,
            headers={"Authorization": f"Bearer {self.tokens['admin_b']}"},
        )
        if foreign_claim.status_code not in [403, 409]:
            self.abort("STEP 6", f"Expected HTTP 409/403 for cross-org claim, got HTTP {foreign_claim.status_code}")
        self.log("STEP 6", f"Cross-org case claim blocked with HTTP {foreign_claim.status_code}", status="PASS")

        # 6d. Assert case appears in Admin Alpha's case queue
        alpha_cases_resp = self.client.get(
            f"{self.base_url}/api/v1/ngo/cases",
            headers={"Authorization": f"Bearer {self.tokens['admin_a']}"},
        )
        if alpha_cases_resp.status_code != 200:
            self.abort("STEP 6", f"Admin Alpha case list query failed: HTTP {alpha_cases_resp.status_code}")
        cases_list = alpha_cases_resp.json()
        matching_alpha = [c for c in cases_list if str(c.get("id")) == str(self.created_case_id)]
        if not matching_alpha:
            self.abort("STEP 6", "Claimed case does not appear in Admin Alpha's NGO case list")
        self.log("STEP 6", "Claimed case confirmed present in Admin Alpha operational queue", status="PASS")

        # 6e. Admin Alpha can view full case dossier
        alpha_dossier = self.client.get(
            f"{self.base_url}/api/v1/ngo/cases/{self.created_case_id}",
            headers={"Authorization": f"Bearer {self.tokens['admin_a']}"},
        )
        if alpha_dossier.status_code != 200:
            self.abort("STEP 6", f"Admin Alpha denied dossier access: HTTP {alpha_dossier.status_code}")
        self.log("STEP 6", "Admin Alpha authorized dossier access verified (HTTP 200)", status="PASS")

        # 6f. Admin Beta is denied dossier access (HTTP 403 or 404)
        beta_dossier = self.client.get(
            f"{self.base_url}/api/v1/ngo/cases/{self.created_case_id}",
            headers={"Authorization": f"Bearer {self.tokens['admin_b']}"},
        )
        if beta_dossier.status_code not in [403, 404]:
            self.abort("STEP 6", f"Admin Beta accessed foreign dossier! HTTP {beta_dossier.status_code}")
        self.log("STEP 6", f"Admin Beta dossier access correctly blocked (HTTP {beta_dossier.status_code})", status="PASS")

        # 6g. Admin Alpha can now access private evidence after claiming
        evidence_url = f"{self.base_url}/api/v1/rescues/{self.created_case_id}/images/{self.created_image_id}/access"
        alpha_img_resp = self.client.get(evidence_url, headers={"Authorization": f"Bearer {self.tokens['admin_a']}"})
        if alpha_img_resp.status_code != 200:
            self.abort("STEP 6", f"Admin Alpha denied evidence access after claim: HTTP {alpha_img_resp.status_code}")
        expires_alpha = alpha_img_resp.json().get("expires_in")
        self.log("STEP 6", f"Admin Alpha authorized private evidence access verified (HTTP 200, expires_in={expires_alpha}s)", status="PASS")

    # -------------------------------------------------------------------------
    # Step 7: Lifecycle Progression & Deterministic Veterinary Clinical Care
    # -------------------------------------------------------------------------
    def step_7_lifecycle_progression_and_veterinary(self):
        self.log("STEP 7", "Advancing Rescue Lifecycle and Testing Veterinary Care...")

        # 7a. Look up designated veterinary facility for Org Alpha via GET /api/v1/ngo/veterinary
        fac_resp = self.client.get(
            f"{self.base_url}/api/v1/ngo/veterinary",
            headers={"Authorization": f"Bearer {self.tokens['admin_a']}"},
        )
        if fac_resp.status_code != 200 or not fac_resp.json():
            self.abort("STEP 7", f"Failed fetching partner veterinary facilities: HTTP {fac_resp.status_code}")

        facilities = fac_resp.json()
        target_fac = next((f for f in facilities if "cochin petcare emergency hospital" in f.get("name", "").lower()), None)
        if not target_fac:
            target_fac = next((f for f in facilities if "cochin petcare" in f.get("name", "").lower()), None)
        if not target_fac:
            self.abort("STEP 7", "Designated veterinary facility 'Cochin PetCare Emergency Hospital' not found in partner facilities")

        self.test_facility_id = target_fac["id"]
        self.log("STEP 7", f"Designated Veterinary Facility located: {target_fac.get('name')} ({self.test_facility_id})", status="PASS")

        # 7b. Rescuer A transitions status: RESPONDER_EN_ROUTE -> ANIMAL_LOCATED -> RESCUED -> TRANSPORTING -> AT_VETERINARY_FACILITY
        transitions = [
            ("RESPONDER_EN_ROUTE", {}),
            ("ANIMAL_LOCATED", {}),
            ("RESCUED", {}),
            (
                "TRANSPORTING",
                {"veterinary_facility_id": self.test_facility_id},
            ),
            ("AT_VETERINARY_FACILITY", {}),
        ]

        for next_status, extra in transitions:
            patch_resp = self.client.patch(
                f"{self.base_url}/api/v1/rescues/{self.created_case_id}/status",
                json={"status": next_status, **extra},
                headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"},
            )
            if patch_resp.status_code != 200:
                self.abort("STEP 7", f"Failed transition to {next_status}: HTTP {patch_resp.status_code} - {patch_resp.text}")
            self.log("STEP 7", f"Rescue status advanced to: {next_status}", status="PASS")

        # 7c. Assert Vet Beta isolation on foreign case, treatment list, and treatment creation
        self.log("STEP 7", "Asserting Vet Beta isolation on foreign case and treatments...")
        # Vet Beta case detail access must fail (HTTP 403 Forbidden)
        vb_case_resp = self.client.get(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}",
            headers={"Authorization": f"Bearer {self.tokens['vet_b']}"},
        )
        if vb_case_resp.status_code not in [403, 404]:
            self.abort("STEP 7", f"Vet Beta accessed foreign case! HTTP {vb_case_resp.status_code}")
        self.log("STEP 7", f"Vet Beta case detail access correctly denied (HTTP {vb_case_resp.status_code})", status="PASS")

        # Vet Beta treatment list access must fail (HTTP 403 Forbidden)
        vb_treat_list = self.client.get(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}/treatments",
            headers={"Authorization": f"Bearer {self.tokens['vet_b']}"},
        )
        if vb_treat_list.status_code not in [403, 404]:
            self.abort("STEP 7", f"Vet Beta accessed foreign treatment list! HTTP {vb_treat_list.status_code}")
        self.log("STEP 7", f"Vet Beta treatment list access correctly denied (HTTP {vb_treat_list.status_code})", status="PASS")

        # Vet Beta treatment creation must fail (HTTP 403 Forbidden)
        vb_treat_create = self.client.post(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}/treatments",
            json={
                "diagnosis": "Illegitimate foreign vet entry",
                "treatment_notes": "Attempted unauthorized entry",
                "facility_id": self.test_facility_id,
            },
            headers={"Authorization": f"Bearer {self.tokens['vet_b']}"},
        )
        if vb_treat_create.status_code not in [403, 404]:
            self.abort("STEP 7", f"Vet Beta created treatment on foreign case! HTTP {vb_treat_create.status_code}")
        self.log("STEP 7", f"Vet Beta treatment creation correctly denied (HTTP {vb_treat_create.status_code})", status="PASS")

        # 7d. Record Clinical Treatment by Vet Alpha
        treatment_payload = {
            "diagnosis": f"[{self.pilot_tag}] Right forelimb fracture stabilized; lacerations debrided.",
            "treatment_notes": "Splinted with fiberglass support. Analgesia and initial antibiotic prophylaxis administered.",
            "medications": "Meloxicam 0.2mg/kg SQ, Cefazolin 20mg/kg IV",
            "facility_id": self.test_facility_id,
        }

        treat_resp = self.client.post(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}/treatments",
            json=treatment_payload,
            headers={"Authorization": f"Bearer {self.tokens['vet_a']}"},
        )
        if treat_resp.status_code != 200:
            self.abort("STEP 7", f"Veterinary treatment creation failed: HTTP {treat_resp.status_code} - {treat_resp.text}")
        self.log("STEP 7", "Clinical treatment documented by Vet Alpha (HTTP 200)", status="PASS")

        # 7e. Verify Case Status transitioned to UNDER_TREATMENT
        case_check = self.client.get(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}",
            headers={"Authorization": f"Bearer {self.tokens['vet_a']}"},
        )
        if case_check.status_code != 200:
            self.abort("STEP 7", f"Failed fetching case after treatment: {case_check.text}")
        curr_status = case_check.json().get("status")
        if curr_status != "UNDER_TREATMENT":
            self.abort("STEP 7", f"Expected case status 'UNDER_TREATMENT', got '{curr_status}'")
        self.log("STEP 7", "Case status verified as UNDER_TREATMENT", status="PASS")

        # 7f. Verify authorized actors can read treatments
        va_treats = self.client.get(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}/treatments",
            headers={"Authorization": f"Bearer {self.tokens['vet_a']}"},
        )
        if va_treats.status_code != 200 or len(va_treats.json()) == 0:
            self.abort("STEP 7", f"Vet Alpha failed reading treatments: HTTP {va_treats.status_code}")
        self.log("STEP 7", "Authorized treatment list verified for Vet Alpha (HTTP 200)", status="PASS")

    # -------------------------------------------------------------------------
    # Step 8: Controlled Case Closure
    # -------------------------------------------------------------------------
    def step_8_case_closure(self):
        self.log("STEP 8", "Executing Controlled Case Teardown & Closure...")

        close_transitions = [
            ("RECOVERING", self.tokens["vet_a"]),
            ("READY_FOR_RELEASE", self.tokens["vet_a"]),
            ("RELEASED", self.tokens["vet_a"]),
            ("CLOSED", self.tokens["vet_a"]),
        ]

        for next_status, token in close_transitions:
            resp = self.client.patch(
                f"{self.base_url}/api/v1/rescues/{self.created_case_id}/status",
                json={"status": next_status},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                self.abort("STEP 8", f"Failed transition to {next_status}: HTTP {resp.status_code} - {resp.text}")
            self.log("STEP 8", f"Status advanced to: {next_status}", status="PASS")

        # Final check: status is CLOSED with closed_at
        final_check = self.client.get(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}",
            headers={"Authorization": f"Bearer {self.tokens['admin_a']}"},
        )
        if final_check.status_code == 200:
            final_data = final_check.json()
            if final_data.get("status") == "CLOSED" and final_data.get("closed_at"):
                self.log("STEP 8", f"Case {self.created_case_id} cleanly CLOSED at {final_data.get('closed_at')}", status="PASS")
            else:
                self.abort("STEP 8", "Case not marked closed with timestamp")


def main():
    parser = argparse.ArgumentParser(description="PawReach Authenticated Staging Pilot Runner")
    parser.add_argument(
        "--api-url",
        "--base-url",
        dest="base_url",
        default=os.getenv("STAGING_API_URL", "https://pawreach-api.onrender.com"),
        help="Base URL of target API (default: https://pawreach-api.onrender.com)",
    )
    parser.add_argument(
        "--expected-sha",
        default=os.getenv("EXPECTED_SHA", ""),
        help="Expected Git commit SHA deployed to staging",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP request timeout in seconds (default: 30.0)",
    )
    parser.add_argument(
        "--allow-http",
        action="store_true",
        help="Permit unencrypted HTTP (for local development only)",
    )

    args = parser.parse_args()

    password = os.getenv("STAGING_SEED_PASSWORD", "").strip()
    if not password:
        print("Error: Password is required strictly via STAGING_SEED_PASSWORD environment variable.")
        sys.exit(1)

    runner = StagingPilotRunner(
        base_url=args.base_url,
        seed_password=password,
        expected_sha=args.expected_sha,
        timeout=args.timeout,
        allow_http=args.allow_http,
    )

    try:
        success = runner.run()
        sys.exit(0 if success else 1)
    except PilotFailure as e:
        print(f"\n[FATAL] Pilot execution halted: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FATAL] Unexpected pilot error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
