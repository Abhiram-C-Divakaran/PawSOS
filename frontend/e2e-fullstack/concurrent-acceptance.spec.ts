import { test, expect } from '@playwright/test';
import { loginViaApi, authenticatePage, DEFAULT_E2E_PASSWORD, API_BASE_URL } from './helpers';

test.describe('Full-Stack Concurrent Acceptance Flow (Unmocked)', () => {
  test('atomically awards rescue to first responder and rejects second with HTTP 409 Conflict', async ({
    page,
    request,
  }) => {
    // 1. Obtain real auth tokens for Rescuer 1 and Rescuer 2
    const tokenRescuer1 = await loginViaApi(request, 'rescuer1.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    const tokenRescuer2 = await loginViaApi(request, 'rescuer2.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);

    // 2. Fetch pending offers for both rescuers
    const offersRes1 = await request.get(`${API_BASE_URL}/rescuers/me/offers`, {
      headers: { Authorization: `Bearer ${tokenRescuer1.access_token}` },
    });
    expect(offersRes1.ok()).toBeTruthy();
    const offers1 = await offersRes1.json();

    const offersRes2 = await request.get(`${API_BASE_URL}/rescuers/me/offers`, {
      headers: { Authorization: `Bearer ${tokenRescuer2.access_token}` },
    });
    expect(offersRes2.ok()).toBeTruthy();
    const offers2 = await offersRes2.json();

    // Find the pre-staged concurrent case offer for both rescuers
    const offer1 = offers1.find((o: any) => o.case?.case_number === 'E2E-CASE-CONCURRENT-001');
    const offer2 = offers2.find((o: any) => o.case?.case_number === 'E2E-CASE-CONCURRENT-001');

    expect(offer1).toBeDefined();
    expect(offer2).toBeDefined();

    // 3. Rescuer 1 accepts the offer via API
    const accept1 = await request.post(`${API_BASE_URL}/rescuers/me/offers/${offer1.id}/accept`, {
      headers: { Authorization: `Bearer ${tokenRescuer1.access_token}` },
    });
    expect(accept1.status()).toBe(200);

    // 4. Rescuer 2 attempts to accept the offer for the same case -> MUST fail with 409 Conflict
    const accept2 = await request.post(`${API_BASE_URL}/rescuers/me/offers/${offer2.id}/accept`, {
      headers: { Authorization: `Bearer ${tokenRescuer2.access_token}` },
    });
    expect(accept2.status()).toBe(409);

    // 5. Open Rescuer 2's browser dashboard and verify UI state reflects that the mission is no longer active for them
    await authenticatePage(page, 'rescuer2.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    await page.goto('/rescuer');

    // The offer should either no longer be present or show as expired/unavailable
    await page.waitForTimeout(1000);
    const concurrentOfferCard = page.locator('#incoming-dispatch-alerts').getByText('E2E-CASE-CONCURRENT-001');
    await expect(concurrentOfferCard).not.toBeVisible();
  });
});
