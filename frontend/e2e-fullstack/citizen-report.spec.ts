import { test, expect } from '@playwright/test';
import { authenticatePage, DEFAULT_E2E_PASSWORD } from './helpers';

test.describe('Full-Stack Citizen Report Flow (Unmocked)', () => {
  test('authenticates, submits real emergency report, and verifies database persistence & live tracking', async ({
    page,
  }) => {
    // 1. Authenticate as deterministic seeded citizen user
    await authenticatePage(page, 'citizen.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);

    // 2. Navigate to report page
    await page.goto('/report');
    await expect(page.getByText('Report an Animal in Distress')).toBeVisible();

    // Step 1: Species Selection
    await expect(page.getByText('What animal needs help?')).toBeVisible();
    await page.getByRole('button', { name: 'Dog' }).click();
    await page.getByRole('button', { name: 'Continue' }).click();

    // Step 2: Photo Upload (Skip)
    await expect(page.getByText('Capture or Upload a Photo')).toBeVisible();
    await page.getByRole('button', { name: 'Skip / Continue without Photo' }).click();

    // Step 3: Location
    await expect(page.getByText('Animal Location')).toBeVisible();
    const addressInput = page.getByPlaceholder('e.g. Near Linking Road junction, opposite Metro pillar #42');
    await addressInput.fill('Gateway of India, Colaba, Mumbai');

    // Click map to place location pin
    const mapEl = page.locator('.leaflet-container');
    await expect(mapEl).toBeVisible();
    await mapEl.click({ position: { x: 120, y: 120 } });
    await page.getByRole('button', { name: 'Continue' }).click();

    // Step 4: Medical Triage Inputs
    await expect(page.getByText('Visible Emergency Condition')).toBeVisible();
    const bleedingCheckbox = page.getByRole('checkbox', { name: 'Is the animal visibly bleeding?' });
    await bleedingCheckbox.check();

    const descInput = page.getByPlaceholder('Specific animal markings, behavior, exact spot where hidden, etc.');
    await descInput.fill('Real E2E fullstack test: injured dog near tourist entrance, bleeding paw.');
    await page.getByRole('button', { name: 'Review' }).click();

    // Step 5: Review & Submit
    await expect(page.getByText('Review Details Before Dispatch')).toBeVisible();
    const submitBtn = page.getByRole('button', { name: 'Send Rescue Alert' });
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    // Step 6: Real Backend Confirmation
    await expect(page.getByText('Rescue Alert Sent')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('button', { name: 'Track This Rescue Live' })).toBeVisible();

    // 3. Navigate to live tracking page and verify persisted case details
    await page.getByRole('button', { name: 'Track This Rescue Live' }).click();
    await expect(page).toHaveURL(/\/cases\//);
    await expect(page.getByText('Gateway of India, Colaba, Mumbai')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Canine').or(page.getByText('Dog'))).toBeVisible();
  });
});
