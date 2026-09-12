import { test, expect } from '@playwright/test';
import { loginViaApi, authenticatePage, DEFAULT_E2E_PASSWORD, API_BASE_URL } from './helpers';

test.describe('Full-Stack Veterinary Facility Scoping & Clinical Workflow (Unmocked)', () => {
  test('enforces facility isolation, restricts clinical records to vets, persists treatments, and progresses recovery', async ({
    page,
    request,
  }) => {
    // 1. Authenticate Vet A (Facility A), Vet B (Facility B), and Citizen Reporter
    const tokenVetA = await loginViaApi(request, 'vet.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    const tokenVetB = await loginViaApi(request, 'vetB.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    const tokenCitizen = await loginViaApi(request, 'citizen.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);

    // 2. Fetch admitted cases for Vet A: must see Facility A case (E2E-CASE-VET-001), but NOT Facility B case (E2E-CASE-VETB-001)
    const vetACasesRes = await request.get(`${API_BASE_URL}/veterinary/cases`, {
      headers: { Authorization: `Bearer ${tokenVetA.access_token}` },
    });
    expect(vetACasesRes.ok()).toBeTruthy();
    const vetACases = await vetACasesRes.json();

    const caseA = vetACases.find((c: any) => c.case_number === 'E2E-CASE-VET-001');
    const caseB = vetACases.find((c: any) => c.case_number === 'E2E-CASE-VETB-001');
    expect(caseA).toBeDefined();
    expect(caseB).toBeUndefined(); // Facility scoping check

    // 3. Facility Isolation: Vet A attempts to access or treat Facility B's case -> MUST return 403
    const vetBCasesRes = await request.get(`${API_BASE_URL}/veterinary/cases`, {
      headers: { Authorization: `Bearer ${tokenVetB.access_token}` },
    });
    expect(vetBCasesRes.ok()).toBeTruthy();
    const caseBData = (await vetBCasesRes.json()).find((c: any) => c.case_number === 'E2E-CASE-VETB-001');
    expect(caseBData).toBeDefined();

    const crossFacilityTreatment = await request.post(`${API_BASE_URL}/rescues/${caseBData.id}/treatments`, {
      headers: { Authorization: `Bearer ${tokenVetA.access_token}` },
      data: {
        facility_id: caseA.veterinary_facility_id,
        diagnosis: 'Unauthorized cross-facility assessment attempt',
        treatment_notes: 'Should fail with 403',
      },
    });
    expect(crossFacilityTreatment.status()).toBe(403);

    // 4. Role Restriction: Citizen role attempts to record treatment -> MUST return 403
    const citizenTreatment = await request.post(`${API_BASE_URL}/rescues/${caseA.id}/treatments`, {
      headers: { Authorization: `Bearer ${tokenCitizen.access_token}` },
      data: {
        facility_id: caseA.veterinary_facility_id,
        diagnosis: 'Citizen diagnosis attempt',
        treatment_notes: 'Should fail with 403',
      },
    });
    expect(citizenTreatment.status()).toBe(403);

    // 5. Browser UI: Vet A logs in and records medical treatment on authorized case
    await authenticatePage(page, 'vet.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    await page.goto('/vet');
    await expect(page.getByText('Veterinary Emergency & Treatment Portal')).toBeVisible();

    await expect(page.getByText('E2E-CASE-VET-001')).toBeVisible({ timeout: 15000 });
    await page.getByText('E2E-CASE-VET-001').click();

    await expect(page.getByText('Clinical Diagnosis & Medical Treatment')).toBeVisible();

    const diagInput = page.getByPlaceholder('e.g. Compound fracture of left tibia, hypovolemic shock');
    await diagInput.fill('Severe dehydration and hind-limb laceration');

    const medsInput = page.getByPlaceholder('e.g. Cefazolin 25mg/kg IV, Meloxicam 0.2mg/kg SC, Tramadol');
    await medsInput.fill('Meloxicam 0.2mg/kg SC, Amoxicillin-Clavulanate 20mg/kg, Ringer Lactate IV');

    const notesInput = page.getByPlaceholder('Describe clinical observations, surgical interventions, prognosis...');
    await notesInput.fill('Wound debrided and sutured under sedation. Animal recovering peacefully in kennel.');

    const submitBtn = page.getByRole('button', { name: 'Record Medical Treatment' });
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    await expect(page.getByText(/Medical assessment and treatment recorded/i)).toBeVisible({ timeout: 10000 });

    // 6. Verify treatment persistence and status progression in real PostgreSQL state
    const treatmentsRes = await request.get(`${API_BASE_URL}/rescues/${caseA.id}/treatments`, {
      headers: { Authorization: `Bearer ${tokenVetA.access_token}` },
    });
    expect(treatmentsRes.ok()).toBeTruthy();
    const treatments = await treatmentsRes.json();
    expect(treatments.length).toBeGreaterThanOrEqual(1);
    const latestTreatment = treatments[treatments.length - 1];
    expect(latestTreatment.diagnosis).toBe('Severe dehydration and hind-limb laceration');
    expect(latestTreatment.medications).toContain('Meloxicam');

    // Case should now be in UNDER_TREATMENT
    const updatedCaseRes = await request.get(`${API_BASE_URL}/rescues/${caseA.id}`, {
      headers: { Authorization: `Bearer ${tokenVetA.access_token}` },
    });
    expect(updatedCaseRes.ok()).toBeTruthy();
    const updatedCase = await updatedCaseRes.json();
    expect(updatedCase.status).toBe('UNDER_TREATMENT');
  });
});
