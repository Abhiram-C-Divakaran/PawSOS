import { test, expect } from '@playwright/test';

test.describe('Concurrent Acceptance Conflict Protection E2E', () => {
  const offerId = 'offer-concurrent-777';
  const caseId = 'case-concurrent-777';

  test.beforeEach(async ({ page }) => {
    // Set authenticated session for Rescuer 2
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-rescuer-2-token');
    });

    // Mock auth/me for Rescuer 2
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'rescuer-user-222',
          email: 'rescuer2@pawsos.org',
          full_name: 'Rescuer Two',
          phone: '+919876543266',
          role: 'RESCUER',
          organization_id: 'org-1111',
          is_active: true,
        }),
      });
    });

    // Mock facilities
    await page.route('**/api/v1/veterinary/facilities**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    // Mock rescuer location and nearby rescues
    await page.route('**/api/v1/rescuers/me/location**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    });
    await page.route('**/api/v1/rescues/nearby**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });

    // Mock notifications
    await page.route('**/api/v1/notifications**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });
  });

  test('should display conflict toast when another responder claims the offer first', async ({ page }) => {
    // Initially offer appears in inbox
    let offerClaimed = false;
    await page.route('**/api/v1/rescuers/me/offers', async (route) => {
      if (offerClaimed) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: offerId,
              rescue_case_id: caseId,
              expires_at: new Date(Date.now() + 120000).toISOString(),
              status: 'OFFERED',
              dispatch_score: 89,
              case: {
                id: caseId,
                case_number: 'CASE-CONCURRENT-001',
                species: 'Canine',
                triage_priority: 'CRITICAL',
                triage_reason: 'Hit by car on highway',
                address_text: 'Eastern Express Highway',
                latitude: 19.1234,
                longitude: 72.8567,
              },
            },
          ]),
        });
      }
    });

    // Accept fails with HTTP 409 Conflict because Responder 1 claimed it
    await page.route(`**/api/v1/rescuers/offers/${offerId}/accept`, async (route) => {
      offerClaimed = true;
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'This rescue assignment has already been claimed by another responder.',
        }),
      });
    });

    await page.goto('/rescuer');

    // Offer is visible
    await expect(page.getByText('CASE-CONCURRENT-001')).toBeVisible();

    // Click Accept Rescue
    const acceptBtn = page.getByRole('button', { name: /Accept Rescue/i });
    await expect(acceptBtn).toBeVisible();
    await acceptBtn.click();

    // Verify error notification is displayed
    await expect(
      page.getByText(/This rescue assignment has already been claimed|This offer expired or was claimed by another responder/i)
    ).toBeVisible();
  });
});
