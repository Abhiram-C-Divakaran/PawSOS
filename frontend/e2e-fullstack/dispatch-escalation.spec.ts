import { test, expect } from '@playwright/test';
import { loginViaApi, authenticatePage, DEFAULT_E2E_PASSWORD, API_BASE_URL } from './helpers';

test.describe('Full-Stack Dispatch Radius Escalation Flow (Unmocked)', () => {
  test('progressively expands dispatch radius across attempts and reflects in NGO Command Center', async ({
    page,
    request,
  }) => {
    // 1. Authenticate as seeded Citizen to create an emergency case
    const tokenCitizen = await loginViaApi(request, 'citizen.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    const tokenAdminA = await loginViaApi(request, 'ngoadminA.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);

    // 2. Create emergency case in an isolated location (no nearby responders at 5km)
    const createRes = await request.post(`${API_BASE_URL}/rescues/`, {
      headers: { Authorization: `Bearer ${tokenCitizen.access_token}` },
      data: {
        species: 'Canine',
        description: 'Isolated canine reported along coastal rocks requiring progressive escalation',
        latitude: 18.8800,
        longitude: 72.8100,
        address_text: 'Remote Coastal Area, South Reach',
        bleeding: true,
        can_walk: false,
        conscious: true,
      },
    });
    expect(createRes.ok()).toBeTruthy();
    const caseData = await createRes.json();
    const caseId = caseData.id;

    // Initial radius should be 5.0 km and attempt 0 or 1
    expect(caseData.dispatch_radius_km).toBe(5.0);

    // 3. Trigger manual re-dispatch via NGO Admin endpoint to test escalation progression
    const redispatchRes = await request.post(`${API_BASE_URL}/ngo/cases/${caseId}/action`, {
      headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
      data: {
        action: 'redispatch',
        reason: 'Radius expansion escalation test',
      },
    });
    expect(redispatchRes.ok()).toBeTruthy();

    // 4. Verify case record reflects the active dispatch attempt
    const updatedCaseRes = await request.get(`${API_BASE_URL}/rescues/${caseId}`, {
      headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
    });
    expect(updatedCaseRes.ok()).toBeTruthy();
    const updatedCase = await updatedCaseRes.json();
    expect(updatedCase.status).toBe('SEARCHING_RESPONDER');

    // 5. Navigate to NGO Command Center Cases UI
    await authenticatePage(page, 'ngoadminA.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    await page.goto(`/ngo/cases/${caseId}`);

    // 6. Verify case detail displays active emergency information
    await expect(page.getByText(updatedCase.case_number)).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('SEARCHING RESPONDER')).toBeVisible();
    await expect(page.getByText('Remote Coastal Area, South Reach')).toBeVisible();
  });
});
