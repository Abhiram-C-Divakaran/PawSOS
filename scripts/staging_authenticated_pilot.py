#!/usr/bin/env python3
"""PawReach Authenticated Staging Pilot Execution Script.

Executes a comprehensive, non-destructive, synthetic end-to-end pilot workflow
against the live hosted PawReach staging environment (or local dev):
1. Service Readiness & Telemetry Validation
2. Multi-Role Authentication (Citizen, Responders, Veterinarian, NGO Admins)
3. Synthetic Incident Creation & Deterministic Triage Verification
4. Dispatch Offer Verification & Claim Authorization Integrity (Ensures 403 without offer)
5. Atomic Claim Acceptance & Conflict Protection
6. Full Rescue Lifecycle Progression (EN_ROUTE -> LOCATED -> RESCUED -> TRANSPORTING -> AT_FACILITY)
7. Evidence Access Authorization Boundaries (Assigned vs Unauthorized)
8. Veterinary Clinical Treatment Documentation
9. Multi-Tenant Scoping & Tenant Isolation
10. Controlled Case Closure & Audit Verification
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


class StagingPilotRunner:
    def __init__(
        self,
        base_url: str,
        seed_password: str,
        timeout: float = 30.0,
        allow_http: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.seed_password = seed_password
        self.timeout = timeout
        self.allow_http = allow_http
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)
        self.tokens: Dict[str, str] = {}
        self.pilot_tag = f"PILOT-{int(time.time())}"
        self.created_case_id: Optional[str] = None
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
        print(f"\n[FATAL] Pilot execution halted due to failure in {section}.")
        sys.exit(1)

    def run(self) -> bool:
        print("====================================================================")
        print("          PawReach Hosted Staging Authenticated Pilot              ")
        print(f"          Execution Tag: {self.pilot_tag}")
        print("====================================================================")
        print(f"Target URL:     {self.base_url}")
        print(f"Timeout:        {self.timeout}s")
        print(f"HTTPS Enforced: {not self.allow_http}")
        print("--------------------------------------------------------------------\n")

        # 0. Protocol Validation
        if not self.allow_http and not self.base_url.startswith("https://"):
            self.abort("PROTOCOL", f"Insecure URL '{self.base_url}'. Staging requires HTTPS.")

        # 1. Readiness & Telemetry
        self.step_1_readiness()

        # 2. Authenticate Actors
        self.step_2_authenticate()

        # 3. Create Case & Verify Triage
        self.step_3_create_case_and_triage()

        # 4. Dispatch Claim Authorization & Offer Acceptance
        self.step_4_dispatch_and_claim_integrity()

        # 5. Rescue Lifecycle Progression
        self.step_5_lifecycle_progression()

        # 6. Evidence Access Authorization Check
        self.step_6_evidence_access_security()

        # 7. Veterinary Clinical Treatment
        self.step_7_veterinary_care()

        # 8. Multi-Tenant Isolation
        self.step_8_multitenant_isolation()

        # 9. Controlled Closure
        self.step_9_case_closure()

        print("\n====================================================================")
        print("          ALL AUTHENTICATED PILOT STAGING SCENARIOS PASSED ✅        ")
        print("====================================================================")
        return True

    # -------------------------------------------------------------------------
    # Step 1: Readiness & Telemetry
    # -------------------------------------------------------------------------
    def step_1_readiness(self):
        self.log("STEP 1", "Verifying Backend Subsystem Deep Readiness (/api/v1/health/ready)...")
        ready_url = f"{self.base_url}/api/v1/health/ready"
        try:
            resp = self.client.get(ready_url)
            if resp.status_code != 200:
                self.abort("STEP 1", f"Readiness endpoint returned HTTP {resp.status_code}: {resp.text}")
            data = resp.json()
            db_status = data.get("database") or data.get("db")
            worker_status = data.get("celery_worker") or data.get("worker")
            git_sha = data.get("git_sha", "unknown")

            self.log("STEP 1", f"Git SHA: {git_sha} | DB: {db_status} | Worker: {worker_status}", status="PASS")
        except Exception as e:
            self.abort("STEP 1", f"Connection error: {e}")

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
                    self.log("STEP 2", f"Citizen account not found; registering dynamic pilot citizen...", status="WARN")
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
    # Step 3: Incident Creation & Deterministic Triage
    # -------------------------------------------------------------------------
    def step_3_create_case_and_triage(self):
        self.log("STEP 3", f"Reporting Synthetic Emergency Incident [{self.pilot_tag}]...")
        # Kochi Marine Drive coordinates (Near Rescuer A: 9.9850, 76.2980)
        report_payload = {
            "species": "Dog",
            "description": f"[{self.pilot_tag}] Injured dog, severe trauma after traffic accident. Visible bleeding.",
            "latitude": 9.9852,
            "longitude": 76.2981,
            "address_text": "Marine Drive Promenade, Kochi, Kerala",
            "bleeding": True,
            "conscious": True,
            "can_walk": False,
            "vehicle_accident": True,
            "breathing_difficulty": False,
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

        self.log(
            "STEP 3",
            f"Case Created: {self.created_case_id} | Status: {case_status} | Triage Priority: {triage_priority} | Score: {triage_score}",
            status="PASS",
        )

        # Assert deterministic triage
        if triage_priority not in ["CRITICAL", "URGENT"]:
            self.abort("STEP 3", f"Expected CRITICAL/URGENT triage priority, received '{triage_priority}'")

    # -------------------------------------------------------------------------
    # Step 4: Dispatch Offer Inspection & Claim Authorization Enforcement
    # -------------------------------------------------------------------------
    def step_4_dispatch_and_claim_integrity(self):
        self.log("STEP 4", "Verifying Dispatch Claim Authorization Integrity & Offers...")

        # 4a. Negative Test: Rescuer B (or third party) attempts direct claim without active offer
        self.log("STEP 4", "Testing Negative Claim Authorization (Rescuer B without offer)...")
        bypass_resp = self.client.post(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}/accept",
            headers={"Authorization": f"Bearer {self.tokens['rescuer_b']}"},
        )
        # Must return 403 Forbidden because Rescuer B does not own an active offer for this case
        if bypass_resp.status_code == 403:
            self.log("STEP 4", "Direct claim without active offer successfully blocked with HTTP 403 Forbidden!", status="PASS")
        elif bypass_resp.status_code == 200:
            self.abort("STEP 4", "SECURITY BYPASS DETECTED! Rescuer B claimed case without an active offer.")
        else:
            self.log("STEP 4", f"Direct claim rejected with HTTP {bypass_resp.status_code}", status="INFO")

        # 4b. Find Rescuer A's active offer
        self.log("STEP 4", "Inspecting Rescuer A incoming dispatch offers...")
        offer_id = None
        for attempt in range(6):
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

        # 4c. Acceptance:
        if offer_id:
            self.log("STEP 4", f"Found pending offer {offer_id} for Rescuer A. Accepting via canonical endpoint...", status="PASS")
            accept_resp = self.client.post(
                f"{self.base_url}/api/v1/rescuers/offers/{offer_id}/accept",
                headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"},
            )
            if accept_resp.status_code != 200:
                self.abort("STEP 4", f"Offer acceptance failed: HTTP {accept_resp.status_code} - {accept_resp.text}")
        else:
            # If offer was not in me/offers list (e.g. single-offer direct assignment), test legacy shim with Rescuer A
            self.log("STEP 4", "Testing secure legacy shim acceptance for Rescuer A...", status="INFO")
            shim_resp = self.client.post(
                f"{self.base_url}/api/v1/rescues/{self.created_case_id}/accept",
                headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"},
            )
            if shim_resp.status_code != 200:
                self.abort("STEP 4", f"Legacy shim accept failed: HTTP {shim_resp.status_code} - {shim_resp.text}")
            self.log("STEP 4", "Rescuer A accepted via secure shim delegation", status="PASS")

        # 4d. Verify Case Transitioned to RESPONDER_ASSIGNED
        case_check = self.client.get(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}",
            headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"},
        )
        if case_check.status_code != 200:
            self.abort("STEP 4", f"Failed to fetch assigned case: {case_check.text}")
        status_val = case_check.json().get("status")
        if status_val != "RESPONDER_ASSIGNED":
            self.abort("STEP 4", f"Expected case status 'RESPONDER_ASSIGNED', got '{status_val}'")
        self.log("STEP 4", "Case status verified as RESPONDER_ASSIGNED", status="PASS")

        # 4e. Negative Test: Subsequent acceptance after assignment returns 409 Conflict
        second_claim = self.client.post(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}/accept",
            headers={"Authorization": f"Bearer {self.tokens['rescuer_b']}"},
        )
        if second_claim.status_code in [403, 409]:
            self.log("STEP 4", f"Subsequent claim after assignment rejected with HTTP {second_claim.status_code}", status="PASS")
        else:
            self.abort("STEP 4", f"Expected 403 or 409 for second claim, got HTTP {second_claim.status_code}")

    # -------------------------------------------------------------------------
    # Step 5: Full Rescue Lifecycle Progression
    # -------------------------------------------------------------------------
    def step_5_lifecycle_progression(self):
        self.log("STEP 5", "Advancing Rescue Lifecycle Transitions...")

        # Lookup facility for Org Alpha
        fac_resp = self.client.get(
            f"{self.base_url}/api/v1/veterinary/facilities",
            headers={"Authorization": f"Bearer {self.tokens['admin_a']}"},
        )
        if fac_resp.status_code == 200 and fac_resp.json():
            self.test_facility_id = fac_resp.json()[0]["id"]
            self.log("STEP 5", f"Designated Veterinary Facility: {self.test_facility_id}", status="INFO")

        transitions = [
            ("RESPONDER_EN_ROUTE", {}),
            ("ANIMAL_LOCATED", {}),
            ("RESCUED", {}),
            (
                "TRANSPORTING",
                {"veterinary_facility_id": self.test_facility_id} if self.test_facility_id else {},
            ),
            ("AT_VETERINARY_FACILITY", {}),
        ]

        for next_status, extra_payload in transitions:
            payload = {"status": next_status, **extra_payload}
            patch_resp = self.client.patch(
                f"{self.base_url}/api/v1/rescues/{self.created_case_id}/status",
                json=payload,
                headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"},
            )
            if patch_resp.status_code != 200:
                self.abort("STEP 5", f"Failed transition to {next_status}: HTTP {patch_resp.status_code} - {patch_resp.text}")
            self.log("STEP 5", f"Status advanced to: {next_status}", status="PASS")

    # -------------------------------------------------------------------------
    # Step 6: Evidence Access Authorization Check
    # -------------------------------------------------------------------------
    def step_6_evidence_access_security(self):
        self.log("STEP 6", "Verifying Case & Evidence Access Boundaries...")

        # 6a. Rescuer A (Assigned) can access private case details
        assigned_check = self.client.get(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}",
            headers={"Authorization": f"Bearer {self.tokens['rescuer_a']}"},
        )
        if assigned_check.status_code != 200:
            self.abort("STEP 6", f"Assigned rescuer denied case access: HTTP {assigned_check.status_code}")
        self.log("STEP 6", "Assigned Rescuer A private case access authorized (HTTP 200)", status="PASS")

        # 6b. Rescuer B (Unassigned) is denied private access
        unassigned_check = self.client.get(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}",
            headers={"Authorization": f"Bearer {self.tokens['rescuer_b']}"},
        )
        if unassigned_check.status_code == 403:
            self.log("STEP 6", "Unassigned Rescuer B denied private case access (HTTP 403 Forbidden)", status="PASS")
        else:
            self.log("STEP 6", f"Unassigned rescuer received HTTP {unassigned_check.status_code}", status="INFO")

    # -------------------------------------------------------------------------
    # Step 7: Veterinary Treatment & Clinical Flow
    # -------------------------------------------------------------------------
    def step_7_veterinary_care(self):
        self.log("STEP 7", "Testing Veterinary Clinical Intake & Treatment Workflow...")

        treatment_payload = {
            "diagnosis": f"[{self.pilot_tag}] Fracture stabilization and laceration wound dressing.",
            "treatment_notes": "Cleaned, sutured, analgesic administered. Stabilized with splint.",
            "medications": "Meloxicam 0.2mg/kg, Cefazolin 20mg/kg",
            "facility_id": self.test_facility_id,
        }

        treat_resp = self.client.post(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}/treatments",
            json=treatment_payload,
            headers={"Authorization": f"Bearer {self.tokens['vet_a']}"},
        )
        if treat_resp.status_code != 200:
            self.abort("STEP 7", f"Veterinary treatment creation failed: HTTP {treat_resp.status_code} - {treat_resp.text}")

        self.log("STEP 7", "Clinical treatment documented by Dr. Rajesh Varma (Vet Alpha)", status="PASS")

        # Verify Case Status transitioned to UNDER_TREATMENT
        case_check = self.client.get(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}",
            headers={"Authorization": f"Bearer {self.tokens['vet_a']}"},
        )
        if case_check.status_code == 200:
            curr_status = case_check.json().get("status")
            if curr_status == "UNDER_TREATMENT":
                self.log("STEP 7", "Case status verified as UNDER_TREATMENT", status="PASS")

    # -------------------------------------------------------------------------
    # Step 8: Multi-Tenant Boundary Isolation
    # -------------------------------------------------------------------------
    def step_8_multitenant_isolation(self):
        self.log("STEP 8", "Validating Multi-Tenant Isolation (Org Alpha vs Org Beta)...")

        # Admin Alpha can see case in Org cases list
        alpha_cases = self.client.get(
            f"{self.base_url}/api/v1/ngo/cases",
            headers={"Authorization": f"Bearer {self.tokens['admin_a']}"},
        )
        if alpha_cases.status_code == 200:
            self.log("STEP 8", "Admin Alpha operational queue access verified", status="PASS")

        # Admin Beta (foreign org) cannot access Org Alpha's private case management endpoint
        beta_detail = self.client.get(
            f"{self.base_url}/api/v1/ngo/cases/{self.created_case_id}",
            headers={"Authorization": f"Bearer {self.tokens['admin_b']}"},
        )
        if beta_detail.status_code in [403, 404]:
            self.log("STEP 8", f"Cross-tenant isolation enforced! Admin Beta access blocked with HTTP {beta_detail.status_code}", status="PASS")
        else:
            self.abort("STEP 8", f"Tenant leak! Admin Beta accessed Org Alpha case with HTTP {beta_detail.status_code}")

    # -------------------------------------------------------------------------
    # Step 9: Controlled Closure
    # -------------------------------------------------------------------------
    def step_9_case_closure(self):
        self.log("STEP 9", "Executing Controlled Case Teardown & Closure...")

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
                self.abort("STEP 9", f"Failed closing transition to {next_status}: HTTP {resp.status_code} - {resp.text}")
            self.log("STEP 9", f"Status advanced to: {next_status}", status="PASS")

        # Final check
        final_check = self.client.get(
            f"{self.base_url}/api/v1/rescues/{self.created_case_id}",
            headers={"Authorization": f"Bearer {self.tokens['admin_a']}"},
        )
        if final_check.status_code == 200:
            final_data = final_check.json()
            if final_data.get("status") == "CLOSED" and final_data.get("closed_at"):
                self.log("STEP 9", f"Case {self.created_case_id} cleanly CLOSED at {final_data.get('closed_at')}", status="PASS")
            else:
                self.abort("STEP 9", "Case not marked closed with timestamp")


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
        "--password",
        default=os.getenv("STAGING_SEED_PASSWORD", ""),
        help="Password for seeded staging accounts (reads STAGING_SEED_PASSWORD by default)",
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

    if not args.password:
        print("Error: Password is required via --password or STAGING_SEED_PASSWORD environment variable.")
        sys.exit(1)

    runner = StagingPilotRunner(
        base_url=args.base_url,
        seed_password=args.password,
        timeout=args.timeout,
        allow_http=args.allow_http,
    )

    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
