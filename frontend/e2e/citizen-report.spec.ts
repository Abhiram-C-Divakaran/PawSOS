import { test, expect } from '@playwright/test';

test.describe('Citizen Report Workflow E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Set authenticated citizen session
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-citizen-token');
    });

    // Mock auth/me for citizen role
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '11111111-0000-0000-0000-111111111111',
          email: 'citizen@pawsos.org',
          full_name: 'Priya Sharma',
          phone: '+919876543210',
          role: 'CITIZEN',
          is_active: true,
        }),
      });
    });

    // Mock auth/refresh
    await page.route('**/api/v1/auth/refresh', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock-citizen-token',
          refresh_token: 'mock-refresh-token',
          token_type: 'bearer',
        }),
      });
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

  test('should complete end-to-end emergency report submission', async ({ page }) => {
    // Intercept image upload
    await page.route('**/api/v1/uploads/image', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          image_url: 'https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=800',
        }),
      });
    });

    // Intercept all rescue endpoints (create, get, timeline, list)
    await page.route(/\/api\/v1\/rescues/, async (route) => {
      const url = route.request().url();
      const method = route.request().method();

      if (method === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'case-e2e-1234',
            case_number: 'CASE-2026-9999',
            species: 'Dog',
            status: 'SEARCHING_RESPONDER',
            triage_priority: 'CRITICAL',
            triage_reason: 'Severe vehicular impact, bleeding heavily',
            latitude: 19.0760,
            longitude: 72.8777,
            address_text: 'Linking Road, Bandra West, Mumbai',
            description: 'Injured dog found near sidewalk.',
            created_at: new Date().toISOString(),
          }),
        });
      } else if (url.includes('/timeline')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: 'time-1',
              status: 'SEARCHING_RESPONDER',
              timestamp: new Date().toISOString(),
              notes: 'Dispatch engine broadcasting to nearby responders',
            },
          ]),
        });
      } else if (url.includes('/case-e2e-1234')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'case-e2e-1234',
            case_number: 'CASE-2026-9999',
            species: 'Dog',
            status: 'SEARCHING_RESPONDER',
            triage_priority: 'CRITICAL',
            triage_reason: 'Severe vehicular impact, bleeding heavily',
            latitude: 19.0760,
            longitude: 72.8777,
            address_text: 'Linking Road, Bandra West, Mumbai',
            description: 'Injured dog found near sidewalk.',
            created_at: new Date().toISOString(),
            images: [],
            timeline: [],
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        });
      }
    });

    await page.goto('/report');

    // Step 1: Species Selection
    await expect(page.getByText('What animal needs help?')).toBeVisible();
    await page.getByRole('button', { name: 'Dog' }).click();
    await page.getByRole('button', { name: 'Continue' }).click();

    // Step 2: Photo upload (skip)
    await expect(page.getByText('Capture or Upload a Photo')).toBeVisible();
    await page.getByRole('button', { name: 'Skip / Continue without Photo' }).click();

    // Step 3: Location
    await expect(page.getByText('Animal Location')).toBeVisible();
    const addressInput = page.getByPlaceholder('e.g. Near Linking Road junction, opposite Metro pillar #42');
    await addressInput.fill('Linking Road, Bandra West, Mumbai');
    // Click map container to place pin
    const mapEl = page.locator('.leaflet-container');
    await expect(mapEl).toBeVisible();
    await mapEl.click({ position: { x: 100, y: 100 } });
    await page.getByRole('button', { name: 'Continue' }).click();

    // Step 4: Medical Triage
    await expect(page.getByText('Visible Emergency Condition')).toBeVisible();
    // Toggle bleeding
    const bleedingCheckbox = page.getByRole('checkbox', { name: 'Is the animal visibly bleeding?' });
    await bleedingCheckbox.check();
    const descInput = page.getByPlaceholder('Specific animal markings, behavior, exact spot where hidden, etc.');
    await descInput.fill('Injured dog found near sidewalk, needs immediate help.');
    await page.getByRole('button', { name: 'Review' }).click();

    // Step 5: Review & Submit
    await expect(page.getByText('Review Details Before Dispatch')).toBeVisible();
    const submitBtn = page.getByRole('button', { name: 'Send Rescue Alert' });
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    // Step 6: Confirmation
    await expect(page.getByText('Rescue Alert Sent')).toBeVisible();
    await expect(page.getByText('CASE-2026-9999')).toBeVisible();
    await expect(page.getByText('CRITICAL')).toBeVisible();
    await expect(page.getByText('SEARCHING RESPONDER')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Track This Rescue Live' })).toBeVisible();
  });
});
