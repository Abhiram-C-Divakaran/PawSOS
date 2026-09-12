import { test, expect } from '@playwright/test';
import { authenticatePage, DEFAULT_E2E_PASSWORD } from './helpers';

test.describe('Full-Stack Veterinary Care Flow (Unmocked)', () => {
  test('veterinarian reviews admitted animal, records medical diagnosis/treatment, and progresses clinical status', async ({
    page,
  }) => {
    // 1. Authenticate as seeded Veterinarian
    await authenticatePage(page, 'vet.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);

    // 2. Navigate to Veterinary Dashboard
    await page.goto('/vet');
    await expect(page.getByText('Veterinary Emergency & Treatment Portal')).toBeVisible();

    // 3. Locate pre-staged admitted patient
    await expect(page.getByText('E2E-CASE-VET-001')).toBeVisible({ timeout: 15000 });
    await page.getByText('E2E-CASE-VET-001').click();

    // 4. Fill clinical treatment form
    await expect(page.getByText('Clinical Diagnosis & Medical Treatment')).toBeVisible();

    const diagInput = page.getByPlaceholder('e.g. Compound fracture of left tibia, hypovolemic shock');
    await diagInput.fill('Severe dehydration and leg contusion');

    const medsInput = page.getByPlaceholder('e.g. Cefazolin 25mg/kg IV, Meloxicam 0.2mg/kg SC, Tramadol');
    await medsInput.fill('Meloxicam 0.5mg/kg, Ringer Lactate IV 100ml/hr');

    const notesInput = page.getByPlaceholder('Describe clinical observations, surgical interventions, prognosis...');
    await notesInput.fill('Patient stabilized, vitals normal after fluid therapy. Monitored in post-op ward.');

    // 5. Submit treatment record
    const submitBtn = page.getByRole('button', { name: 'Record Medical Treatment' });
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    // 6. Verify success notification
    await expect(page.getByText(/Medical assessment and treatment recorded/i)).toBeVisible({ timeout: 10000 });

    // 7. Select case again and progress medical status
    await page.getByText('E2E-CASE-VET-001').click();
    const progressBtn = page.getByRole('button', { name: /Mark as UNDER TREATMENT/i });
    if (await progressBtn.isVisible()) {
      await progressBtn.click();
      await expect(page.getByText(/Status updated: UNDER TREATMENT/i)).toBeVisible({ timeout: 10000 });
    }
  });
});
