import { test, expect } from '@playwright/test';
import { loginViaApi, authenticatePage, DEFAULT_E2E_PASSWORD, API_BASE_URL } from './helpers';

test.describe('Full-Stack Cross-Tenant Boundary Defense (Unmocked)', () => {
  test('strictly prevents cross-tenant data leakage and blocks unauthorized tenant escalation', async ({
    page,
    request,
  }) => {
    // 1. Authenticate both Org A Admin and Org B Admin via API
    const tokenAdminA = await loginViaApi(request, 'ngoadminA.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    const tokenAdminB = await loginViaApi(request, 'ngoadminB.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);

    // 2. Fetch Org B's profile to get Org B user IDs
    const orgBMe = await request.get(`${API_BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${tokenAdminB.access_token}` },
    });
    const orgBUserData = await orgBMe.json();
    const orgBUserId = orgBUserData.id;
    const orgBOrgId = orgBUserData.organization_id;

    // 3. Org A Admin attempts cross-tenant responder status update -> MUST be rejected with 403
    const crossTenantUpdate = await request.patch(`${API_BASE_URL}/ngo/responders/${orgBUserId}/status`, {
      headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
      data: { is_active: false },
    });
    expect(crossTenantUpdate.status()).toBe(403);
    const crossErr = await crossTenantUpdate.json();
    expect(crossErr.detail).toContain('CROSS_TENANT_RESPONDER_UPDATE_DENIED');

    // 4. Org A Admin attempts to reassign or adopt a responder to Org B -> MUST be rejected with 403
    const adoptAttempt = await request.patch(`${API_BASE_URL}/ngo/responders/${orgBUserId}/status`, {
      headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
      data: { organization_id: orgBOrgId },
    });
    expect(adoptAttempt.status()).toBe(403);

    // 5. Open Org A Command Center in browser
    await authenticatePage(page, 'ngoadminA.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    await page.goto('/ngo/cases');
    await expect(page.getByText('Rescue Mission Log')).toBeVisible();

    // 6. Confirm Org B's confidential case does NOT leak into Org A UI table
    await page.waitForTimeout(1000);
    const orgBCaseRow = page.getByText('E2E-CASE-ORGB-001');
    await expect(orgBCaseRow).not.toBeVisible();
  });
});
