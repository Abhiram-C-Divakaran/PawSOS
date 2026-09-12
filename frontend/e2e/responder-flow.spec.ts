import { test, expect } from '@playwright/test';

test.describe('Responder Field Workflow E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Set authenticated rescuer session
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-rescuer-token');
    });

    // Mock auth/me for rescuer
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '22222222-0000-0000-0000-222222222222',
          email: 'rescuer@pawsos.org',
          full_name: 'Rahul Deshmukh',
          phone: '+919876543220',
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
        body: JSON.stringify([
          {
            id: 'fac-1',
            name: 'Central Veterinary Emergency Hospital',
            address: 'Dadar West, Mumbai',
            phone: '+919876543299',
            is_24_hours: true,
          },
        ]),
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

  test('should receive dispatch offer, accept mission, and advance rescue status', async ({ page }) => {
    const offerId = 'offer-e2e-888';
    const caseId = 'case-e2e-888';

    // Mock rescuer offers list
    await page.route('**/api/v1/rescuers/me/offers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: offerId,
            rescue_case_id: caseId,
            expires_at: new Date(Date.now() + 180000).toISOString(),
            status: 'OFFERED',
            dispatch_score: 94,
            case: {
              id: caseId,
              case_number: 'CASE-2026-8888',
              species: 'Cat',
              triage_priority: 'CRITICAL',
              triage_reason: 'Stuck in storm drain, breathing difficulty',
              address_text: 'SV Road, Andheri West, Mumbai',
              latitude: 19.1136,
              longitude: 72.8697,
            },
          },
        ]),
      });
    });

    // Mock accept offer
    await page.route(`**/api/v1/rescuers/offers/${offerId}/accept`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'ACCEPTED',
          rescue_case_id: caseId,
        }),
      });
    });

    // Mock active rescue case initial state
    let currentStatus = 'RESPONDER_ASSIGNED';
    await page.route(`**/api/v1/rescues/${caseId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: caseId,
          case_number: 'CASE-2026-8888',
          species: 'Cat',
          status: currentStatus,
          triage_priority: 'CRITICAL',
          triage_reason: 'Stuck in storm drain, breathing difficulty',
          address_text: 'SV Road, Andheri West, Mumbai',
          latitude: 19.1136,
          longitude: 72.8697,
          images: [],
        }),
      });
    });

    // Mock status updates
    await page.route(`**/api/v1/rescues/${caseId}/status`, async (route) => {
      const body = JSON.parse(route.request().postData() || '{}');
      currentStatus = body.status;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: caseId,
          case_number: 'CASE-2026-8888',
          species: 'Cat',
          status: currentStatus,
          triage_priority: 'CRITICAL',
          triage_reason: 'Stuck in storm drain, breathing difficulty',
          address_text: 'SV Road, Andheri West, Mumbai',
          latitude: 19.1136,
          longitude: 72.8697,
          images: [],
        }),
      });
    });

    await page.goto('/rescuer');

    // Verify incoming dispatch alert
    await expect(page.getByText('Incoming Rescue Alerts (1)')).toBeVisible();
    await expect(page.getByText('CASE-2026-8888')).toBeVisible();

    // Accept Rescue
    const acceptBtn = page.getByRole('button', { name: /Accept Rescue/i });
    await expect(acceptBtn).toBeVisible();
    await acceptBtn.click();

    // Verify success toast
    await expect(page.getByText('Dispatch offer accepted! Rescue assigned to you.')).toBeVisible();

    // Verify active case details appear
    await expect(page.getByText('Current Mission Status')).toBeVisible();
    await expect(page.getByText('RESPONDER ASSIGNED')).toBeVisible();

    // Advance to RESPONDER EN ROUTE
    const enRouteBtn = page.getByRole('button', { name: /Mark as RESPONDER EN ROUTE/i });
    await expect(enRouteBtn).toBeVisible();
    await enRouteBtn.click();

    // Verify status changed to RESPONDER EN ROUTE
    await expect(page.getByText('RESPONDER EN ROUTE', { exact: true })).toBeVisible();

    // Advance to ANIMAL LOCATED
    const locatedBtn = page.getByRole('button', { name: /Mark as ANIMAL LOCATED/i });
    await expect(locatedBtn).toBeVisible();
    await locatedBtn.click();

    // Verify status changed to ANIMAL LOCATED
    await expect(page.getByText('ANIMAL LOCATED', { exact: true })).toBeVisible();
  });
});
