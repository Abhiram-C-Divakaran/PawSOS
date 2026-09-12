import { test, expect } from '@playwright/test';
import { loginViaApi, authenticatePage, DEFAULT_E2E_PASSWORD, API_BASE_URL } from './helpers';

test.describe('Full-Stack Concurrent Acceptance Conflict Protection (Unmocked)', () => {
  test('atomically awards rescue to exactly one responder and rejects conflicting request with 409 Conflict', async ({
    page,
    request,
  }) => {
    // 1. Obtain real auth tokens for Rescuer 1, Rescuer 2, and NGO Admin
    const tokenRescuer1 = await loginViaApi(request, 'rescuer1.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    const tokenRescuer2 = await loginViaApi(request, 'rescuer2.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    const tokenAdminA = await loginViaApi(request, 'ngoadminA.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);

    // 2. Fetch pending offers for both rescuers
    const [offersRes1, offersRes2] = await Promise.all([
      request.get(`${API_BASE_URL}/rescuers/me/offers`, {
        headers: { Authorization: `Bearer ${tokenRescuer1.access_token}` },
      }),
      request.get(`${API_BASE_URL}/rescuers/me/offers`, {
        headers: { Authorization: `Bearer ${tokenRescuer2.access_token}` },
      }),
    ]);
    expect(offersRes1.ok()).toBeTruthy();
    expect(offersRes2.ok()).toBeTruthy();

    const offers1 = await offersRes1.json();
    const offers2 = await offersRes2.json();

    const offer1 = offers1.find((o: any) => o.case?.case_number === 'E2E-CASE-CONCURRENT-001');
    const offer2 = offers2.find((o: any) => o.case?.case_number === 'E2E-CASE-CONCURRENT-001');

    expect(offer1).toBeDefined();
    expect(offer2).toBeDefined();
    const caseId = offer1.case.id;

    // 3. Fire simultaneous acceptance requests against PostgreSQL using Promise.all
    // Atomic row locking in backend ensures exactly one winner
    const [res1, res2] = await Promise.all([
      request.post(`${API_BASE_URL}/rescuers/me/offers/${offer1.id}/accept`, {
        headers: { Authorization: `Bearer ${tokenRescuer1.access_token}` },
      }),
      request.post(`${API_BASE_URL}/rescuers/me/offers/${offer2.id}/accept`, {
        headers: { Authorization: `Bearer ${tokenRescuer2.access_token}` },
      }),
    ]);

    const statuses = [res1.status(), res2.status()].sort();
    expect(statuses).toEqual([200, 409]);

    // 4. Verify authoritative database state through NGO Dossier
    const dossierRes = await request.get(`${API_BASE_URL}/ngo/cases/${caseId}`, {
      headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
    });
    expect(dossierRes.ok()).toBeTruthy();
    const dossier = await dossierRes.json();

    expect(dossier.status).toBe('RESPONDER_ASSIGNED');
    expect(dossier.assigned_responder).toBeDefined();
    expect(dossier.assigned_responder.assignment_status).toBe('ACCEPTED');

    // Confirm remaining competing offers are cancelled
    const offersInDossier = dossier.dispatch_offers || [];
    const acceptedOffers = offersInDossier.filter((o: any) => o.status === 'ACCEPTED');
    const cancelledOffers = offersInDossier.filter((o: any) => o.status === 'CANCELLED');

    expect(acceptedOffers.length).toBe(1);
    expect(cancelledOffers.length).toBeGreaterThanOrEqual(1);

    // 5. Open losing responder's dashboard in browser and verify UI reflects non-availability
    const loserEmail = res1.status() === 409 ? 'rescuer1.e2e@pawreach.test' : 'rescuer2.e2e@pawreach.test';
    await authenticatePage(page, loserEmail, DEFAULT_E2E_PASSWORD);
    await page.goto('/rescuer');

    // The claimed offer is no longer available to accept
    await page.waitForTimeout(1000);
    const offerCard = page.locator('#incoming-dispatch-alerts').getByText('E2E-CASE-CONCURRENT-001');
    await expect(offerCard).not.toBeVisible();
  });
});
