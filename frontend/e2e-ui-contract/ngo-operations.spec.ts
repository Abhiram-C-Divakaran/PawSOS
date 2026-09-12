import { test, expect } from '@playwright/test';

test.describe('NGO Command Center Operations E2E', () => {
  const orgId = '33333333-0000-0000-0000-333333333333';
  const caseId = 'case-ngo-001';

  test.beforeEach(async ({ page }) => {
    // Set authenticated NGO Admin session
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-ngo-admin-token');
    });

    // Mock auth/me for NGO Admin
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'admin-user-001',
          email: 'admin@pawreachngo.org',
          full_name: 'Director Amit Roy',
          phone: '+919876543230',
          role: 'NGO_ADMIN',
          organization_id: orgId,
          is_active: true,
        }),
      });
    });

    // Mock system readiness/health
    await page.route('**/api/v1/health/ready', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'healthy',
          database: 'connected',
          redis: 'connected',
          celery: 'running',
          storage: 's3',
          firebase: 'initialized',
          timestamp: new Date().toISOString(),
        }),
      });
    });

    // Mock org profile
    await page.route('**/api/v1/ngo/organization**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: orgId,
          name: 'PawReach Emergency NGO',
          email: 'admin@pawreachngo.org',
          phone: '+919876543230',
          organization_type: 'NGO',
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

  test('should display overview KPIs, list cases, inspect dossier timeline, and perform action', async ({ page }) => {
    // Mock Overview KPIs
    await page.route('**/api/v1/ngo/analytics/overview**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          active_cases: 14,
          critical_cases: 4,
          urgent_cases: 5,
          searching_responder_cases: 3,
          awaiting_responder: 3,
          responders_en_route: 4,
          responders_available: 8,
          responders_assigned: 6,
          under_treatment: 5,
          recovering: 2,
          unresolved_cases: 1,
          closed_today: 3,
          avg_dispatch_seconds: 42.5,
          average_response_minutes: 18.4,
          avg_response_minutes: 18.4,
          avg_completion_minutes: 110.0,
          completion_rate_pct: 88.5,
          responder_availability_pct: 57.1,
          total_cases: 42,
        }),
      });
    });

    // Mock hotspots
    await page.route('**/api/v1/ngo/analytics/hotspots**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    // Mock response-times
    await page.route('**/api/v1/ngo/analytics/response-times**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    // Mock cases list
    await page.route('**/api/v1/ngo/cases**', async (route) => {
      const url = route.request().url();
      if (url.includes(`/ngo/cases/${caseId}`)) {
        return route.continue();
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: caseId,
            case_number: 'CASE-NGO-2026-001',
            species: 'Canine',
            status: 'SEARCHING_RESPONDER',
            triage_priority: 'CRITICAL',
            triage_reason: 'Deep laceration, vehicle collision',
            address_text: 'Juhu Tara Road, Mumbai',
            latitude: 19.0988,
            longitude: 72.8264,
            created_at: new Date(Date.now() - 3600000).toISOString(),
          },
        ]),
      });
    });

    // Mock case dossier detail
    await page.route(`**/api/v1/ngo/cases/${caseId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: caseId,
          case_number: 'CASE-NGO-2026-001',
          species: 'Canine',
          status: 'SEARCHING_RESPONDER',
          triage_priority: 'CRITICAL',
          triage_reason: 'Deep laceration, vehicle collision',
          address_text: 'Juhu Tara Road, Mumbai',
          latitude: 19.0988,
          longitude: 72.8264,
          created_at: new Date(Date.now() - 3600000).toISOString(),
          reporter: {
            full_name: 'Ananya Sen',
            phone: '+919876543299',
          },
          images: [],
          dispatch_offers: [
            {
              id: 'offer-ngo-1',
              rescuer_name: 'Rahul Deshmukh',
              dispatch_score: 95,
              distance_km: 2.4,
              status: 'PENDING',
              offered_at: new Date().toISOString(),
              rejection_reason: null,
            },
          ],
          audit_trail: [
            {
              id: 'audit-1',
              action: 'DISPATCH_WAVE_INITIATED',
              new_value: { reason: 'Automatic dispatch wave 1 initiated' },
              timestamp: new Date().toISOString(),
            },
          ],
          status_history: [
            {
              id: 'hist-1',
              previous_status: null,
              new_status: 'REPORTED',
              created_at: new Date(Date.now() - 3600000).toISOString(),
              notes: 'Initial emergency report received',
            },
          ],
          assignments: [],
          treatments: [],
        }),
      });
    });

    // Mock responders list for action modal
    await page.route('**/api/v1/ngo/responders', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            user_id: 'rescuer-override-1',
            full_name: 'Karan Mehra',
            phone: '+919876543255',
            availability: 'AVAILABLE',
          },
        ]),
      });
    });

    // Mock veterinary facilities for action modal
    await page.route('**/api/v1/ngo/veterinary', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'vet-override-1',
            name: 'Juhu Veterinary Clinic',
            address: 'Juhu, Mumbai',
          },
        ]),
      });
    });

    // Mock administrative action override
    await page.route(`**/api/v1/ngo/cases/${caseId}/actions`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: 'Responder assigned successfully via administrative command.',
        }),
      });
    });

    // 1. Visit Overview
    await page.goto('/ngo');

    // Verify KPIs
    await expect(page.getByText('Active Cases')).toBeVisible();
    await expect(page.getByText('14', { exact: true })).toBeVisible();
    await expect(page.getByText('18.4 min')).toBeVisible();

    // 2. Navigate to Cases
    await page.getByRole('link', { name: /Cases/i }).first().click();
    await expect(page.getByText('CASE-NGO-2026-001')).toBeVisible();

    // 3. Drill down into Case Detail
    await page.getByRole('link', { name: /View Dossier/i }).first().click();

    // Verify Case Dossier
    await expect(page.getByText('Deep laceration, vehicle collision')).toBeVisible();
    await expect(page.getByText('Automatic dispatch wave 1 initiated')).toBeVisible();
    await expect(page.getByText('Rahul Deshmukh')).toBeVisible();

    // 4. Test Administrative Override Action
    const assignBtn = page.getByRole('button', { name: /Manual Assign/i });
    if (await assignBtn.isVisible()) {
      await assignBtn.click();
      const confirmBtn = page.getByRole('button', { name: /Execute & Audit Log/i });
      if (await confirmBtn.isVisible()) {
        await confirmBtn.click();
        await expect(page.getByText(/Responder assigned successfully/i)).toBeVisible();
      }
    }
  });
});
