import { test, expect } from '@playwright/test';
import { loginViaApi, authenticatePage, DEFAULT_E2E_PASSWORD, API_BASE_URL } from './helpers';

test.describe('Full-Stack Cross-Tenant Boundary Defense & Security (Unmocked)', () => {
  test('strictly isolates multi-tenant case dossiers, prevents responder hijacking, and preserves super admin access', async ({
    page,
    request,
  }) => {
    // 1. Authenticate Org A Admin, Org B Admin, and Super Admin
    const tokenAdminA = await loginViaApi(request, 'ngoadminA.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    const tokenAdminB = await loginViaApi(request, 'ngoadminB.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    const tokenSuper = await loginViaApi(request, 'superadmin.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);

    // 2. Fetch Org B's pre-staged confidential case
    const orgBCasesRes = await request.get(`${API_BASE_URL}/ngo/cases`, {
      headers: { Authorization: `Bearer ${tokenAdminB.access_token}` },
    });
    expect(orgBCasesRes.ok()).toBeTruthy();
    const orgBCases = await orgBCasesRes.json();
    const caseOrgB = orgBCases.find((c: any) => c.case_number === 'E2E-CASE-ORGB-001');
    expect(caseOrgB).toBeDefined();

    // 3. Org A Admin attempts to view Org B case dossier -> MUST be rejected with 403 Forbidden
    const crossDossierRes = await request.get(`${API_BASE_URL}/ngo/cases/${caseOrgB.id}`, {
      headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
    });
    expect(crossDossierRes.status()).toBe(403);

    // 4. Org A Admin lists cases -> Org B case must NOT leak into the list
    const orgACasesRes = await request.get(`${API_BASE_URL}/ngo/cases`, {
      headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
    });
    expect(orgACasesRes.ok()).toBeTruthy();
    const orgACases = await orgACasesRes.json();
    const leakedCase = orgACases.find((c: any) => c.case_number === 'E2E-CASE-ORGB-001');
    expect(leakedCase).toBeUndefined();

    // 5. Fetch Org B's responder
    const orgBRespondersRes = await request.get(`${API_BASE_URL}/ngo/responders`, {
      headers: { Authorization: `Bearer ${tokenAdminB.access_token}` },
    });
    expect(orgBRespondersRes.ok()).toBeTruthy();
    const orgBResponders = await orgBRespondersRes.json();
    const responderOrgB = orgBResponders.find((r: any) => r.email === 'rescuerB.e2e@pawreach.test');
    expect(responderOrgB).toBeDefined();

    // 6. Org A Admin attempts to modify Org B responder operational status -> MUST be rejected with 403
    const crossResponderUpdate = await request.patch(
      `${API_BASE_URL}/ngo/responders/${responderOrgB.user_id}/status`,
      {
        headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
        data: { is_active: false },
      }
    );
    expect(crossResponderUpdate.status()).toBe(403);
    const crossErr = await crossResponderUpdate.json();
    expect(crossErr.detail).toContain('Access denied');

    // 7. Org A Admin attempts to reassign Org B responder organization -> MUST be rejected with 403
    const meA = await request.get(`${API_BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
    });
    const orgAId = (await meA.json()).organization_id;

    const adoptAttempt = await request.patch(
      `${API_BASE_URL}/ngo/responders/${responderOrgB.user_id}/status`,
      {
        headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
        data: { organization_id: orgAId },
      }
    );
    expect(adoptAttempt.status()).toBe(403);
    const adoptErr = await adoptAttempt.json();
    expect(adoptErr.detail).toContain('Organization reassignment is restricted to super administrators');

    // 8. Super Admin retains intentional global access to Org B case dossier
    const superDossierRes = await request.get(`${API_BASE_URL}/ngo/cases/${caseOrgB.id}`, {
      headers: { Authorization: `Bearer ${tokenSuper.access_token}` },
    });
    expect(superDossierRes.status()).toBe(200);

    // 9. Browser verification: Open Org A Command Center and verify Org B case is NOT displayed
    await authenticatePage(page, 'ngoadminA.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    await page.goto('/ngo/cases');
    await expect(page.getByText('Rescue Mission Log')).toBeVisible();

    await page.waitForTimeout(1000);
    const orgBCaseCell = page.getByText('E2E-CASE-ORGB-001');
    await expect(orgBCaseCell).not.toBeVisible();
  });
});
