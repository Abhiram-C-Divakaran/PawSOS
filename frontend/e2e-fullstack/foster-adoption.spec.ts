import { test, expect } from '@playwright/test';
import { loginViaApi, authenticatePage, DEFAULT_E2E_PASSWORD, API_BASE_URL } from './helpers';

test.describe('Full-Stack Foster & Adoption Operations (Unmocked)', () => {
  test('foster matching, caregiver offer acceptance, daily care logging, adoption application, and NGO cascade approval', async ({
    page,
    request,
  }) => {
    // -------------------------------------------------------------------------
    // 1. Authenticate Actors
    // -------------------------------------------------------------------------
    const tokenNgo = await loginViaApi(request, 'ngoadminA.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    const tokenCitizen = await loginViaApi(request, 'citizen.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);

    // -------------------------------------------------------------------------
    // 2. NGO Foster Matching & Assignment Dispatch
    // -------------------------------------------------------------------------
    // Find pre-staged recovering case E2E-CASE-FOST-001
    const casesRes = await request.get(
      `${API_BASE_URL}/ngo/cases?search=E2E-CASE-FOST-001`,
      {
        headers: { Authorization: `Bearer ${tokenNgo.access_token}` },
      }
    );
    expect(casesRes.ok()).toBeTruthy();
    const casesList = await casesRes.json();
    const fosterCase = casesList.find(
      (c: any) => c.case_number === 'E2E-CASE-FOST-001'
    );
    expect(fosterCase).toBeDefined();

    // Fetch matching foster homes for this case
    const matchRes = await request.post(`${API_BASE_URL}/ngo/foster/matches`, {
      headers: { Authorization: `Bearer ${tokenNgo.access_token}` },
      data: { case_id: fosterCase.id },
    });
    expect(matchRes.ok()).toBeTruthy();
    const matches = await matchRes.json();
    expect(matches.length).toBeGreaterThan(0);

    const targetHome = matches[0];
    expect(targetHome.foster_home_id).toBeDefined();

    // NGO dispatches foster placement offer
    const offerRes = await request.post(`${API_BASE_URL}/ngo/foster/assignments`, {
      headers: { Authorization: `Bearer ${tokenNgo.access_token}` },
      data: {
        rescue_case_id: fosterCase.id,
        foster_home_id: targetHome.foster_home_id,
        notes: 'Pre-staged foster care candidate ready for transition',
      },
    });
    expect(offerRes.ok()).toBeTruthy();
    const assignmentData = await offerRes.json();
    expect(assignmentData.status).toBe('OFFERED');

    // -------------------------------------------------------------------------
    // 3. Foster Caregiver UI: View & Accept Offer, Submit Care Update
    // -------------------------------------------------------------------------
    await authenticatePage(page, 'foster.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    await page.goto('/foster');
    await expect(page.getByText('Foster Caregiver Hub')).toBeVisible({ timeout: 15000 });

    // Verify offered placement card appears
    await expect(page.getByText('E2E-CASE-FOST-001')).toBeVisible();

    // Accept offer
    const acceptBtn = page.getByRole('button', { name: 'Accept Placement' });
    await expect(acceptBtn).toBeVisible();
    await acceptBtn.click();

    // Switch to Current Animals tab
    await page.getByRole('button', { name: /Current Animals/i }).click();

    // Verify active placement section updates
    await expect(page.getByText('E2E-CASE-FOST-001')).toBeVisible();
    const recordUpdateBtn = page.getByRole('button', { name: 'Record Care Update' });
    await expect(recordUpdateBtn).toBeVisible({ timeout: 10000 });
    await recordUpdateBtn.click();

    // Modal opens
    await expect(page.getByPlaceholder(/Describe appetite, recovery progress/i)).toBeVisible();
    await page.getByPlaceholder(/Describe appetite, recovery progress/i).fill('Puppy is recovering wonderfully, playing and eating heartily.');
    await page.getByRole('button', { name: 'Submit Care Update' }).click();

    // Verify modal closes and care log is persisted
    await expect(page.getByText('Puppy is recovering wonderfully')).toBeVisible({ timeout: 10000 });

    // -------------------------------------------------------------------------
    // 4. Public Catalog & Citizen Adoption Application
    // -------------------------------------------------------------------------
    // Authenticate citizen for adoption flow
    await authenticatePage(page, 'citizen.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    await page.goto('/adopt');
    await expect(page.getByText('Give a Rescue Pet a Second Chance')).toBeVisible({ timeout: 15000 });

    // Pre-staged listing "Milo" should be visible in catalog
    await expect(page.getByText('Milo - Gentle Golden Retriever Mix')).toBeVisible();

    // Click Milo card to view detail page
    await page.getByText('Milo - Gentle Golden Retriever Mix').click();
    await expect(page).toHaveURL(/\/adopt\//);
    await expect(page.getByText('About this rescue')).toBeVisible();

    // Click Apply to Adopt
    const applyBtn = page.getByRole('button', { name: /Apply to Adopt/i });
    await expect(applyBtn).toBeVisible();
    await applyBtn.click();
    await expect(page).toHaveURL(/\/apply/);
    await expect(page.getByText('Adoption Application')).toBeVisible();

    // Fill application questionnaire
    await page.getByPlaceholder(/Tell the NGO about your routine/i).fill('Family of three with a private fenced terrace, ready for Milo.');
    await page.getByRole('button', { name: 'Submit Application' }).click();

    // Verify redirect to My Applications dashboard with SUBMITTED status
    await expect(page).toHaveURL(/\/(adoption-applications|my-adoptions)/, { timeout: 15000 });
    await expect(page.getByText('My Adoption Applications')).toBeVisible();
    await expect(page.getByText('Milo - Gentle Golden Retriever Mix')).toBeVisible();
    await expect(page.getByText('SUBMITTED', { exact: true })).toBeVisible();

    // -------------------------------------------------------------------------
    // 5. NGO Review, Scheduling & Transactional Cascade Approval
    // -------------------------------------------------------------------------
    // Query applications via NGO API to get application ID
    const appListRes = await request.get(`${API_BASE_URL}/adoptions/applications`, {
      headers: { Authorization: `Bearer ${tokenNgo.access_token}` },
    });
    expect(appListRes.ok()).toBeTruthy();
    const apps = await appListRes.json();
    const citizenApp = apps.find((a: any) => a.listing_title && a.listing_title.includes('Milo'));
    expect(citizenApp).toBeDefined();
    expect(citizenApp.status).toBe('SUBMITTED');

    // NGO schedules visit
    const visitRes = await request.post(`${API_BASE_URL}/adoptions/applications/${citizenApp.id}/schedule-visit`, {
      headers: { Authorization: `Bearer ${tokenNgo.access_token}` },
      data: {
        visit_date: new Date(Date.now() + 86400000).toISOString(),
        location_type: 'FACILITY',
        visit_address: 'South Mumbai Animal Hospital Adoption Center',
        notes: 'Bring proof of residence and family members',
      },
    });
    expect(visitRes.ok()).toBeTruthy();

    // Non-NGO role (Citizen) attempts to approve application -> MUST return 403
    const unauthorizedDecision = await request.post(`${API_BASE_URL}/adoptions/applications/${citizenApp.id}/decision`, {
      headers: { Authorization: `Bearer ${tokenCitizen.access_token}` },
      data: {
        status: 'APPROVED',
        review_notes: 'Unauthorized approval attempt',
      },
    });
    expect(unauthorizedDecision.status()).toBe(403);

    // NGO Admin executes final adoption approval
    const decisionRes = await request.post(`${API_BASE_URL}/adoptions/applications/${citizenApp.id}/decision`, {
      headers: { Authorization: `Bearer ${tokenNgo.access_token}` },
      data: {
        status: 'APPROVED',
        review_notes: 'Home check passed, family interview complete. Approved for adoption.',
      },
    });
    expect(decisionRes.ok()).toBeTruthy();
    const approvedAppData = await decisionRes.json();
    expect(approvedAppData.status).toBe('APPROVED');

    // -------------------------------------------------------------------------
    // 6. Verify Transactional Cascade Integrity
    // -------------------------------------------------------------------------
    // A. Listing must now be CLOSED
    const listingCheckRes = await request.get(`${API_BASE_URL}/adoptions/listings/${citizenApp.listing_id}`);
    expect(listingCheckRes.ok()).toBeTruthy();
    const listingCheck = await listingCheckRes.json();
    expect(listingCheck.status).toBe('CLOSED');

    // B. Public catalog must NOT include the closed listing by default
    const publicCatalogRes = await request.get(`${API_BASE_URL}/adoptions/listings`);
    expect(publicCatalogRes.ok()).toBeTruthy();
    const publicListings = await publicCatalogRes.json();
    const closedInCatalog = publicListings.find((l: any) => l.id === citizenApp.listing_id);
    expect(closedInCatalog).toBeUndefined();

    // C. Underlying rescue case must now have status ADOPTED
    const updatedCaseRes = await request.get(`${API_BASE_URL}/rescues/${citizenApp.rescue_case_id}`, {
      headers: { Authorization: `Bearer ${tokenNgo.access_token}` },
    });
    expect(updatedCaseRes.ok()).toBeTruthy();
    const updatedCase = await updatedCaseRes.json();
    expect(updatedCase.status).toBe('ADOPTED');
  });
});
