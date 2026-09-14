import { test, expect } from '@playwright/test';

test.describe('Phase 3A: Foster & Adoption Operations UI Contract', () => {
  test('Foster Caregiver Flow: View profile, accept offer, and record care update', async ({ page }) => {
    // Authenticate as FOSTER user
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-foster-token');
    });

    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'foster-user-1',
          full_name: 'Priya Deshmukh',
          email: 'priya.foster@pawreach.org',
          phone: '+919811223399',
          role: 'FOSTER',
          is_active: true,
          is_verified: true,
        }),
      });
    });

    await page.route('**/api/v1/notifications**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    // Mock foster profile
    await page.route('**/api/v1/foster/profile', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'home-101',
          caregiver_id: 'foster-user-1',
          locality: 'Bandra West, Mumbai',
          capacity: 2,
          current_occupancy: 0,
          accepted_species: 'Dog, Cat',
          medical_care_supported: true,
          availability_status: 'AVAILABLE',
          verified: true,
        }),
      });
    });

    // Mock assignments: initial OFFERED
    let assignmentStatus = 'OFFERED';
    await page.route('**/api/v1/foster/assignments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'assign-101',
            status: assignmentStatus,
            notes: 'Quiet rest area required after hip surgery',
            created_at: new Date().toISOString(),
            start_date: assignmentStatus === 'ACTIVE' ? new Date().toISOString() : null,
            rescue_case: {
              id: 'case-hip-1',
              case_number: 'PR-FOST-99',
              species: 'Dog',
              description: 'Post-surgical hip recovery',
              status: assignmentStatus === 'ACTIVE' ? 'FOSTER_CARE' : 'RECOVERING',
            },
            care_updates: [],
          },
        ]),
      });
    });

    await page.route('**/api/v1/foster/assignments/assign-101/accept', async (route) => {
      assignmentStatus = 'ACTIVE';
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'assign-101', status: 'ACTIVE' }),
      });
    });

    await page.route('**/api/v1/foster/assignments/assign-101/updates', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'upd-1', notes: 'Ate all meals and rested comfortably' }),
      });
    });

    // Navigate to /foster
    await page.goto('/foster');
    await expect(page.getByText('Foster Caregiver Hub')).toBeVisible();
    await expect(page.getByText('Verified Partner')).toBeVisible();
    await expect(page.getByText('PR-FOST-99')).toBeVisible();
    await expect(page.getByText('Quiet rest area required')).toBeVisible();

    // Accept Placement
    const acceptBtn = page.getByRole('button', { name: 'Accept Placement' });
    await expect(acceptBtn).toBeVisible();
    await acceptBtn.click();

    // Switch to active tab
    await page.getByRole('button', { name: 'Current Animals' }).click();
    await expect(page.getByText('PR-FOST-99')).toBeVisible();
    await expect(page.getByText('Record Care Update')).toBeVisible();
  });

  test('Citizen Public Flow: Browse adoption catalog, view details, and apply', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-citizen-token');
    });

    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'citizen-user-1',
          full_name: 'Ananya Roy',
          email: 'ananya@example.com',
          phone: '+919877770001',
          role: 'CITIZEN',
          is_active: true,
          is_verified: true,
        }),
      });
    });

    await page.route('**/api/v1/notifications**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    const mockListing = {
      id: 'listing-201',
      animal_id: 'animal-201',
      rescue_case_id: 'case-201',
      organization_id: 'org-1',
      title: 'Bella - Loving Companion',
      public_description: 'Gentle and affectionate golden mix looking for a loving home.',
      species: 'Dog',
      sex: 'Female',
      approx_age: '1.5 years',
      colour: 'Golden',
      sterilization_status: 'Spayed',
      vaccination_status: 'Complete',
      medical_summary: 'Full veterinary clearance and vaccinated against rabies and DHPPi.',
      organization_name: 'PawReach Mumbai Animal Care',
      locality: 'Juhu, Mumbai',
      status: 'PUBLISHED',
      published_at: new Date().toISOString(),
    };

    await page.route('**/api/v1/adoptions', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([mockListing]),
      });
    });

    await page.route('**/api/v1/adoptions/listing-201', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockListing),
      });
    });

    await page.route('**/api/v1/adoptions/listings/listing-201/apply', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'app-301', status: 'SUBMITTED' }),
      });
    });

    await page.route('**/api/v1/adoptions/my-applications', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'app-301',
            status: 'SUBMITTED',
            created_at: new Date().toISOString(),
            listing: mockListing,
            visits: [],
          },
        ]),
      });
    });

    // 1. Visit Catalog
    await page.goto('/adopt');
    await expect(page.getByText('Give a Rescue Pet a Second Chance')).toBeVisible();
    await expect(page.getByText('Bella - Loving Companion')).toBeVisible();

    // 2. Click through to details
    await page.getByText('Bella - Loving Companion').click();
    await expect(page.getByRole('heading', { name: 'Bella - Loving Companion' })).toBeVisible();
    await expect(page.getByText(/Full veterinary clearance/i)).toBeVisible();

    // 3. Click Apply
    await page.getByRole('button', { name: /Apply to Adopt Bella/i }).click();
    await expect(page.getByRole('heading', { name: 'Adoption Application' })).toBeVisible();

    // 4. Submit Questionnaire
    await page.getByPlaceholder(/Tell the NGO about your routine/i).fill(
      'Our family has experience with dogs, lives in a quiet house, and works from home.'
    );
    await page.getByRole('button', { name: 'Submit Application' }).click();

    // 5. Lands on My Applications
    await expect(page).toHaveURL('/adoption-applications');
    await expect(page.getByText('My Adoption Applications')).toBeVisible();
    await expect(page.getByText('SUBMITTED', { exact: true })).toBeVisible();
  });

  test('NGO Command Center: Review application, schedule visit, and approve', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'mock-ngo-admin-token');
    });

    await page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'ngo-admin-1',
          full_name: 'Coordinator Sharma',
          role: 'NGO_ADMIN',
          organization_id: 'org-1',
          is_active: true,
          is_verified: true,
        }),
      });
    });

    await page.route('**/api/v1/ngo/organization', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'org-1', name: 'PawReach Mumbai Animal Care', is_active: true }),
      });
    });

    await page.route('**/api/v1/health/ready', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'ready', environment: 'staging', services: {} }),
      });
    });

    await page.route('**/api/v1/notifications**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.route('**/api/v1/ngo/adoptions/listings', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'l-1',
            title: 'Charlie - Loving Rescue',
            species: 'Dog',
            locality: 'Andheri West',
            status: 'PUBLISHED',
          },
        ]),
      });
    });

    await page.route('**/api/v1/ngo/adoptions/eligible-cases', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.route('**/api/v1/ngo/adoptions/applications', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'app-999',
            status: 'SUBMITTED',
            applicant: {
              full_name: 'Kavita Menon',
              phone: '+919812345678',
              email: 'kavita@example.com',
            },
            listing: {
              title: 'Charlie - Loving Rescue',
            },
            housing_type: 'Independent House',
            has_fenced_garden: true,
            has_other_pets: false,
            family_members_count: 3,
            reason_for_adoption: 'Dedicated home with large yard',
          },
        ]),
      });
    });

    await page.route('**/api/v1/ngo/adoptions/applications/app-999/approve', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'app-999', status: 'APPROVED' }),
      });
    });

    await page.goto('/ngo/adoptions');
    await expect(page.getByText('Adoption Operations')).toBeVisible();
    await expect(page.getByText('Kavita Menon')).toBeVisible();
    await expect(page.getByText('Approve & Finalize')).toBeVisible();

    // Click Approve opens confirmation modal
    await page.getByText('Approve & Finalize').click();
    await expect(page.getByText(/Automatic Cascade Action/i)).toBeVisible();
    await expect(page.getByText(/Transition animal status from READY_FOR_ADOPTION → ADOPTED/i)).toBeVisible();
  });
});
