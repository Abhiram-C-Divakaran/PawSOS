import { test, expect } from '@playwright/test';

test.describe('Multi-Tenant Isolation & Security E2E', () => {
  const foreignCaseId = 'case-foreign-tenant-999';

  test.beforeEach(async ({ page }) => {
    // Set authenticated session for NGO B admin
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-ngo-b-token');
    });

    // Mock auth/me as NGO B
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'admin-ngo-b-001',
          email: 'admin@secondngo.org',
          full_name: 'Director NGO B',
          phone: '+919876543250',
          role: 'NGO_ADMIN',
          organization_id: 'org-b-2222',
          is_active: true,
        }),
      });
    });

    // Mock health
    await page.route('**/api/v1/health/ready', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'ready', database: 'connected' }),
      });
    });

    // Mock org profile
    await page.route('**/api/v1/ngo/organization**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'org-b-2222',
          name: 'Second NGO Organization',
          email: 'contact@secondngo.org',
          phone: '+919876543250',
          organization_type: 'NGO',
        }),
      });
    });

    // Mock responders and veterinary lists
    await page.route('**/api/v1/ngo/responders**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });
    await page.route('**/api/v1/ngo/veterinary**', async (route) => {
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

  test('should enforce multi-tenant isolation when attempting to view foreign NGO case', async ({ page }) => {
    // Foreign case detail returns 403 Forbidden
    await page.route(`**/api/v1/ngo/cases/${foreignCaseId}`, async (route) => {
      await route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Access denied. Case does not belong to your organization.',
        }),
      });
    });

    // Navigate directly to the foreign case URL
    await page.goto(`/ngo/cases/${foreignCaseId}`);

    // Verify error state is clearly displayed in UI
    await expect(page.locator('#case-error-state')).toBeVisible();
    await expect(page.locator('#case-error-state')).toContainText('Access Denied or Case Not Found');
    await expect(page.locator('#case-error-state')).toContainText('This rescue case may belong to another organization');

    // Verify safe navigation button exists
    const backBtn = page.getByRole('button', { name: /Back to Organization Cases/i });
    await expect(backBtn).toBeVisible();
  });
});
