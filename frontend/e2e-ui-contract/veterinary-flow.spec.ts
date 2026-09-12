import { test, expect } from '@playwright/test';

test.describe('Veterinary Clinical Workflow E2E', () => {
  const caseId = 'case-vet-101';

  test.beforeEach(async ({ page }) => {
    // Set authenticated Vet session
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-vet-token');
    });

    // Mock auth/me for Veterinarian
    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'vet-user-101',
          email: 'dr.sharma@vetcare.org',
          full_name: 'Dr. Radhika Sharma, BVSc',
          phone: '+919876543240',
          role: 'VETERINARIAN',
          organization_id: 'org-vet-1',
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
            id: 'fac-vet-101',
            name: 'Apex 24/7 Animal Trauma Center',
            address: 'Andheri East, Mumbai',
            phone: '+919876543288',
            is_24_hours: true,
          },
        ]),
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

  test('should view inpatient queue, admit case, and record clinical treatment plan', async ({ page }) => {
    // Mock veterinary cases queue
    await page.route('**/api/v1/veterinary/cases', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: caseId,
            case_number: 'CASE-VET-2026-101',
            species: 'Canine',
            status: 'AT_VETERINARY_FACILITY',
            triage_priority: 'CRITICAL',
            triage_reason: 'Compound fracture, left hind leg',
            address_text: 'Western Express Highway, Mumbai',
            latitude: 19.1197,
            longitude: 72.8464,
            veterinary_facility_id: 'fac-vet-101',
            images: [],
          },
        ]),
      });
    });

    // Mock treatment post
    await page.route(`**/api/v1/rescues/${caseId}/treatments`, async (route) => {
      const body = JSON.parse(route.request().postData() || '{}');
      expect(body.diagnosis).toContain('Compound left tibial fracture');
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'treat-001',
          rescue_case_id: caseId,
          diagnosis: body.diagnosis,
          treatment_notes: body.treatment_notes,
          medications: body.medications,
          facility_id: 'fac-vet-101',
          created_at: new Date().toISOString(),
        }),
      });
    });

    await page.goto('/vet');

    // Verify Inpatient registry
    await expect(page.getByText('Veterinary Care & Clinical Inpatient Registry')).toBeVisible();
    await expect(page.getByText('CASE-VET-2026-101')).toBeVisible();

    // Click to select case
    await page.getByText('CASE-VET-2026-101').click();

    // Verify medical record form opens
    await expect(page.getByText(/Medical Record: CASE-VET-2026-101/)).toBeVisible();

    // Fill diagnosis
    const diagnosisInput = page.getByPlaceholder('e.g. Femur fracture, dehydration, laceration');
    await diagnosisInput.fill('Compound left tibial fracture with mild shock');

    // Fill medications
    const medsInput = page.getByPlaceholder(/Meloxicam 0.2mg\/kg/);
    await medsInput.fill('Meloxicam 0.2mg/kg, Tramadol 2mg/kg, Ceftriaxone 25mg/kg');

    // Fill clinical notes
    const notesInput = page.getByPlaceholder(/Enter examination findings/);
    await notesInput.fill('Cleaned and debrided wound under sedation. Applied external splint and started IV fluids.');

    // Submit clinical record
    const submitBtn = page.getByRole('button', { name: /Log Medical Assessment & Start Treatment/i });
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    // Verify success toast notification
    await expect(page.getByText(/Medical assessment and treatment recorded/i)).toBeVisible();
  });
});
