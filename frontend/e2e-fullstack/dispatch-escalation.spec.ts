import { test, expect, APIRequestContext } from '@playwright/test';
import { loginViaApi, authenticatePage, DEFAULT_E2E_PASSWORD, API_BASE_URL } from './helpers';

/**
 * Bounded polling helper waiting for background Celery worker to expand case dispatch radius.
 * Does NOT call any manual redispatch endpoint.
 */
async function waitForDispatchRadius(
  request: APIRequestContext,
  caseId: string,
  expectedRadius: number,
  token: string,
  timeoutMs = 25000
) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const res = await request.get(`${API_BASE_URL}/rescues/${caseId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok()) {
      const data = await res.json();
      if (data.dispatch_radius_km === expectedRadius) {
        return data;
      }
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Timeout waiting for case ${caseId} to reach radius ${expectedRadius}km`);
}

/**
 * Bounded polling helper waiting for background Celery worker to transition case status.
 */
async function waitForCaseStatus(
  request: APIRequestContext,
  caseId: string,
  expectedStatus: string,
  token: string,
  timeoutMs = 25000
) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const res = await request.get(`${API_BASE_URL}/rescues/${caseId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok()) {
      const data = await res.json();
      if (data.status === expectedStatus) {
        return data;
      }
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Timeout waiting for case ${caseId} to reach status ${expectedStatus}`);
}

test.describe('Full-Stack Automatic Dispatch Escalation & Exhaustion Flow (Unmocked)', () => {
  test('naturally expires offers, auto-escalates radius via background worker, creates wave offers, and transitions to UNRESOLVED upon exhaustion', async ({
    page,
    request,
  }) => {
    // 1. Authenticate seeded Citizen and NGO Admin A
    const tokenCitizen = await loginViaApi(request, 'citizen.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    const tokenAdminA = await loginViaApi(request, 'ngoadminA.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);

    // 2. Create emergency case at Gateway of India, Colaba (lat: 18.9220, lng: 72.8340)
    // Rescuer 1 (~0.5km) & Rescuer 2 (~1.1km) are within 5km radius.
    // Rescuer 3 (~8.5km away in Worli) is OUTSIDE 5km radius but INSIDE 10km radius.
    const createRes = await request.post(`${API_BASE_URL}/rescues/`, {
      headers: { Authorization: `Bearer ${tokenCitizen.access_token}` },
      data: {
        species: 'Canine',
        description: 'Injured street puppy near Colaba waterfront requiring natural Celery escalation',
        latitude: 18.9220,
        longitude: 72.8340,
        address_text: 'Colaba Waterfront, Mumbai',
        bleeding: true,
        can_walk: false,
        conscious: true,
      },
    });
    expect(createRes.ok()).toBeTruthy();
    const createdCase = await createRes.json();
    const caseId = createdCase.id;

    // 3. Verify Initial State: Case creation automatically initiates dispatch
    // Status is SEARCHING_RESPONDER, radius is 5.0km, dispatch_attempt is 1
    const initialRes = await request.get(`${API_BASE_URL}/rescues/${caseId}`, {
      headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
    });
    expect(initialRes.ok()).toBeTruthy();
    const initialData = await initialRes.json();
    expect(initialData.status).toBe('SEARCHING_RESPONDER');
    expect(initialData.dispatch_radius_km).toBe(5.0);
    expect(initialData.dispatch_attempt).toBe(1);

    // Verify initial offers (Wave 1) were generated for eligible responders within 5km, but NOT Rescuer 3 (at ~8.5km)
    const dossierRes1 = await request.get(`${API_BASE_URL}/ngo/cases/${caseId}`, {
      headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
    });
    expect(dossierRes1.ok()).toBeTruthy();
    const dossier1 = await dossierRes1.json();
    const wave1Offers = dossier1.dispatch_offers || [];
    expect(wave1Offers.length).toBeGreaterThan(0);
    for (const off of wave1Offers) {
      expect(off.offered_at).toBeTruthy();
      expect(off.expires_at).toBeTruthy();
      expect(off.status).toBe('PENDING');
      expect(off.rescuer_name).not.toBe('E2E Rescuer Wave Two');
    }

    // 4. ALLOW OFFERS TO EXPIRE NATURALLY VIA BACKGROUND CELERY WORKER
    // Do NOT call redispatch! Wait for Celery Beat and worker to expire offers and expand radius to 10 km.
    const escalatedCase = await waitForDispatchRadius(request, caseId, 10.0, tokenAdminA.access_token);
    expect(escalatedCase.dispatch_radius_km).toBe(10.0);
    expect(escalatedCase.dispatch_attempt).toBe(2);

    // 5. PROVE OFFER EXPIRY & NEXT-WAVE CREATION VIA REAL POSTGRESQL STATE
    const dossierRes2 = await request.get(`${API_BASE_URL}/ngo/cases/${caseId}`, {
      headers: { Authorization: `Bearer ${tokenAdminA.access_token}` },
    });
    expect(dossierRes2.ok()).toBeTruthy();
    const dossier2 = await dossierRes2.json();
    const allOffers = dossier2.dispatch_offers || [];

    // Prior wave offers must transition to EXPIRED with expired_at timestamp recorded
    const expiredWave1 = allOffers.filter((o: any) => o.status === 'EXPIRED');
    expect(expiredWave1.length).toBeGreaterThan(0);
    for (const expOffer of expiredWave1) {
      expect(expOffer.expired_at).toBeTruthy();
    }

    // Next wave: Rescuer 3 (at 8.5km) is now within 10km radius and MUST receive a new offer
    const rescuer3Offer = allOffers.find((o: any) => o.rescuer_name === 'E2E Rescuer Wave Two');
    expect(rescuer3Offer).toBeDefined();
    expect(rescuer3Offer.status).toBe('PENDING');
    expect(rescuer3Offer.distance_km).toBeGreaterThan(5.0);
    expect(rescuer3Offer.distance_km).toBeLessThanOrEqual(10.0);
    expect(rescuer3Offer.offered_at).toBeTruthy();
    expect(rescuer3Offer.expires_at).toBeTruthy();

    // Verify responders already offered in Wave 1 do not receive duplicate active offers in Wave 2
    const pendingWave2Offers = allOffers.filter((o: any) => o.status === 'PENDING');
    expect(pendingWave2Offers.length).toBe(1);
    expect(pendingWave2Offers[0].rescuer_name).toBe('E2E Rescuer Wave Two');

    // 6. PROVE DISPATCH EXHAUSTION (SEARCHING_RESPONDER -> UNRESOLVED)
    // Wait for subsequent radii (20km, 40km) to expire naturally without manual intervention
    const unresolvedCase = await waitForCaseStatus(request, caseId, 'UNRESOLVED', tokenAdminA.access_token);
    expect(unresolvedCase.status).toBe('UNRESOLVED');

    // 7. Verify NGO Command Center UI reflects the terminal UNRESOLVED dispatch state
    await authenticatePage(page, 'ngoadminA.e2e@pawreach.test', DEFAULT_E2E_PASSWORD);
    await page.goto(`/ngo/cases/${caseId}`);

    await expect(page.getByText(unresolvedCase.case_number)).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('Colaba Waterfront, Mumbai')).toBeVisible();
    await expect(page.getByText('UNRESOLVED')).toBeVisible();
  });
});
