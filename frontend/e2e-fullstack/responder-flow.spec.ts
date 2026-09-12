import { test, expect } from '@playwright/test';
import { authenticatePage, DEFAULT_E2E_PASSWORD, API_BASE_URL } from './helpers';

test.describe('Full-Stack Responder Flow (Unmocked)', () => {
  test('responder views incoming offer, accepts, and advances rescue through field states to vet handoff', async ({
    page,
  }) => {
    // 1. Authenticate as seeded rescuer 1
    const rescuerEmail = 'rescuer1.e2e@pawreach.test';
    const authData = await authenticatePage(page, rescuerEmail, DEFAULT_E2E_PASSWORD);

    // 2. Create a dedicated unassigned emergency case via API to ensure a fresh offer
    const caseRes = await page.request.post(`${API_BASE_URL}/rescues/`, {
      headers: {
        Authorization: `Bearer ${authData.access_token}`,
      },
      data: {
        species: 'Canine',
        description: 'Street puppy trapped near Colaba market',
        latitude: 18.9220,
        longitude: 72.8340,
        address_text: 'Colaba Market, Mumbai',
        bleeding: false,
        can_walk: false,
        conscious: true,
      },
    });
    expect(caseRes.ok()).toBeTruthy();
    const createdCase = await caseRes.json();

    // 3. Trigger dispatch engine to generate offer for nearby rescuer 1
    const dispatchRes = await page.request.post(`${API_BASE_URL}/dispatch/cases/${createdCase.id}/trigger`, {
      headers: {
        Authorization: `Bearer ${authData.access_token}`,
      },
    });
    expect(dispatchRes.ok()).toBeTruthy();

    // 4. Navigate to Rescuer Dashboard
    await page.goto('/rescuer');
    await expect(page.getByText('Responder Operations Dashboard')).toBeVisible();

    // 5. Verify incoming offer arrives in UI
    const offerAlert = page.locator('#incoming-dispatch-alerts');
    await expect(offerAlert).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(createdCase.case_number)).toBeVisible();

    // 6. Click Accept Rescue
    const acceptBtn = page.getByRole('button', { name: 'Accept Rescue' }).first();
    await expect(acceptBtn).toBeVisible();
    await acceptBtn.click();

    // 7. Verify mission activates on dashboard
    await expect(page.getByText('Active Rescue Mission')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(createdCase.case_number)).toBeVisible();

    // 8. Progressively advance field statuses:
    // En Route -> Located -> Rescued -> Transporting -> At Veterinary Facility
    const markEnRoute = page.getByRole('button', { name: /Mark as RESPONDER EN ROUTE/i });
    if (await markEnRoute.isVisible()) {
      await markEnRoute.click();
    }

    const markLocated = page.getByRole('button', { name: /Mark as ANIMAL LOCATED/i });
    await expect(markLocated).toBeVisible({ timeout: 10000 });
    await markLocated.click();

    const markRescued = page.getByRole('button', { name: /Mark as RESCUED/i });
    await expect(markRescued).toBeVisible({ timeout: 10000 });
    await markRescued.click();

    // Verify veterinary facility selector appears when rescued/transporting
    await expect(page.getByText('Select Veterinary Destination')).toBeVisible({ timeout: 10000 });

    const markTransport = page.getByRole('button', { name: /Mark as TRANSPORTING/i });
    await expect(markTransport).toBeVisible();
    await markTransport.click();

    const markAtVet = page.getByRole('button', { name: /Mark as AT VETERINARY FACILITY/i });
    await expect(markAtVet).toBeVisible({ timeout: 10000 });
    await markAtVet.click();

    // 9. Verify case is successfully handed off and active mission clears
    await expect(page.getByText(/Status updated: AT VETERINARY FACILITY/i)).toBeVisible({ timeout: 10000 });

    // 10. Verify authoritative backend database state via API
    const finalCaseRes = await page.request.get(`${API_BASE_URL}/rescues/${createdCase.id}`, {
      headers: { Authorization: `Bearer ${authData.access_token}` },
    });
    expect(finalCaseRes.ok()).toBeTruthy();
    const finalCase = await finalCaseRes.json();
    expect(finalCase.status).toBe('AT_VETERINARY_FACILITY');
  });
});
