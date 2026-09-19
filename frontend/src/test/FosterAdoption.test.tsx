import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { FosterDashboard } from '../pages/FosterDashboard';
import { AdoptionBrowse } from '../pages/AdoptionBrowse';
import { AdoptionDetail } from '../pages/AdoptionDetail';
import { AdoptionApplicationPage } from '../pages/AdoptionApplicationPage';
import { MyAdoptionApplications } from '../pages/MyAdoptionApplications';
import { NGOAdoptions } from '../pages/ngo/NGOAdoptions';
import api from '../services/api';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock('../context/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 'test-user-1',
      full_name: 'Test Citizen',
      role: 'CITIZEN',
      is_active: true,
      is_verified: true,
    },
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

describe('Phase 3A: Foster & Adoption Components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('FosterDashboard Component', () => {
    it('renders caregiver verified home profile and placement offers', async () => {
      const mockHome = {
        id: 'home-1',
        caregiver_id: 'test-user-1',
        locality: 'Bandra West',
        capacity: 2,
        current_occupancy: 0,
        availability_status: 'AVAILABLE',
        verified: true,
        accepted_species: 'Dog, Cat',
        medical_care_supported: true,
      };

      const mockAssignments = [
        {
          id: 'assign-1',
          status: 'OFFERED',
          notes: 'Gentle recovery required',
          created_at: '2026-09-15T00:00:00Z',
          rescue_case: {
            id: 'case-1',
            case_number: 'PR-FOST-01',
            species: 'Dog',
            description: 'Fractured leg in cast',
            status: 'RECOVERING',
          },
        },
      ];

      (api.get as any).mockImplementation((url: string) => {
        if (url.includes('/foster/profile')) return Promise.resolve({ data: mockHome });
        if (url.includes('/foster/assignments')) return Promise.resolve({ data: mockAssignments });
        return Promise.resolve({ data: [] });
      });

      render(
        <MemoryRouter>
          <FosterDashboard />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Foster Caregiver Hub')).toBeInTheDocument();
        expect(screen.getByText('Verified Partner')).toBeInTheDocument();
        expect(screen.getByText('PR-FOST-01')).toBeInTheDocument();
        expect(screen.getByText('Accept Placement')).toBeInTheDocument();
      });

      // Accept offer interaction
      (api.post as any).mockResolvedValueOnce({ data: { status: 'ACTIVE' } });
      const acceptBtn = screen.getByText('Accept Placement');
      fireEvent.click(acceptBtn);

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith('/foster/assignments/assign-1/accept');
      });
    });
  });

  describe('AdoptionBrowse Component', () => {
    it('renders public adoption catalog and filters listings', async () => {
      const mockListings = [
        {
          id: 'list-1',
          animal_id: 'anim-1',
          rescue_case_id: 'case-1',
          organization_id: 'org-1',
          title: 'Brownie - Playful Pup',
          public_description: 'Loving rescued puppy vaccinated and ready',
          species: 'Dog',
          locality: 'Colaba, Mumbai',
          organization_name: 'PawReach Mumbai Care',
          sterilization_status: 'Neutered',
          vaccination_status: 'Complete',
          status: 'PUBLISHED',
        },
        {
          id: 'list-2',
          animal_id: 'anim-2',
          rescue_case_id: 'case-2',
          organization_id: 'org-1',
          title: 'Whiskers - Calm Cat',
          public_description: 'Quiet indoor cat',
          species: 'Cat',
          locality: 'Bandra, Mumbai',
          organization_name: 'PawReach Mumbai Care',
          status: 'PUBLISHED',
        },
      ];

      (api.get as any).mockImplementation((url: string) => {
        if (url.includes('/adoptions')) return Promise.resolve({ data: mockListings });
        return Promise.resolve({ data: [] });
      });

      render(
        <MemoryRouter>
          <AdoptionBrowse />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Brownie - Playful Pup')).toBeInTheDocument();
        expect(screen.getByText('Whiskers - Calm Cat')).toBeInTheDocument();
      });

      // Filter by species
      const catFilterBtn = screen.getByRole('button', { name: 'CAT' });
      fireEvent.click(catFilterBtn);

      expect(screen.queryByText('Brownie - Playful Pup')).not.toBeInTheDocument();
      expect(screen.getByText('Whiskers - Calm Cat')).toBeInTheDocument();
    });
  });

  describe('AdoptionDetail Component', () => {
    it('renders single listing profile details and CTA', async () => {
      const mockDetail = {
        id: 'list-1',
        title: 'Milo - Gentle Golden',
        public_description: 'Sweet family companion rescued from street',
        species: 'Dog',
        locality: 'Andheri',
        organization_name: 'PawReach Welfare',
        sterilization_status: 'Neutered',
        vaccination_status: 'Complete',
        medical_summary: 'Full fracture healing confirmed by vet',
        sex: 'Male',
        approx_age: '2 years',
      };

      (api.get as any).mockImplementation((url: string) => {
        if (url.includes('/adoptions/list-1')) return Promise.resolve({ data: mockDetail });
        return Promise.resolve({ data: [] });
      });

      render(
        <MemoryRouter initialEntries={['/adopt/list-1']}>
          <Routes>
            <Route path="/adopt/:listingId" element={<AdoptionDetail />} />
          </Routes>
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Milo - Gentle Golden')).toBeInTheDocument();
        expect(screen.getByText(/Full fracture healing confirmed/i)).toBeInTheDocument();
        expect(screen.getByText(/Apply to Adopt Milo/i)).toBeInTheDocument();
      });
    });
  });

  describe('AdoptionApplicationPage Component', () => {
    it('submits citizen adoption application questionnaire', async () => {
      const mockDetail = {
        id: 'list-1',
        title: 'Milo - Gentle Golden',
        species: 'Dog',
        organization_name: 'PawReach Welfare',
      };

      (api.get as any).mockImplementation((url: string) => {
        if (url.includes('/adoptions/list-1')) return Promise.resolve({ data: mockDetail });
        return Promise.resolve({ data: [] });
      });
      (api.post as any).mockResolvedValueOnce({ data: { id: 'app-1', status: 'SUBMITTED' } });

      render(
        <MemoryRouter initialEntries={['/adopt/list-1/apply']}>
          <Routes>
            <Route path="/adopt/:listingId/apply" element={<AdoptionApplicationPage />} />
          </Routes>
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Adoption Application')).toBeInTheDocument();
        expect(screen.getByText('Milo - Gentle Golden')).toBeInTheDocument();
      });

      // Fill reason
      const reasonInput = screen.getByPlaceholderText(/Tell the NGO about your routine/i);
      fireEvent.change(reasonInput, { target: { value: 'We have a warm family with large garden and love dogs.' } });

      const submitBtn = screen.getByText('Submit Application');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith(
          expect.stringContaining('/adoptions/listings/list-1/apply'),
          expect.objectContaining({
            reason_for_adoption: 'We have a warm family with large garden and love dogs.',
          })
        );
      });
    });
  });

  describe('MyAdoptionApplications Component', () => {
    it('renders citizen submitted applications and scheduled visits', async () => {
      const mockApps = [
        {
          id: 'app-10',
          status: 'VISIT_SCHEDULED',
          created_at: '2026-09-15T00:00:00Z',
          listing: {
            title: 'Bella - Loving Companion',
          },
          visits: [
            {
              id: 'v-1',
              scheduled_at: '2026-09-18T15:00:00Z',
              location_address: 'Citizen Residence, Juhu',
              notes: 'Please keep all family members present.',
            },
          ],
        },
      ];

      (api.get as any).mockImplementation((url: string) => {
        if (url.includes('/adoptions/my-applications')) return Promise.resolve({ data: mockApps });
        return Promise.resolve({ data: [] });
      });

      render(
        <MemoryRouter>
          <MyAdoptionApplications />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('My Adoption Applications')).toBeInTheDocument();
        expect(screen.getByText('Bella - Loving Companion')).toBeInTheDocument();
        expect(screen.getByText('MEET-AND-GREET SCHEDULED')).toBeInTheDocument();
        expect(screen.getByText(/Citizen Residence, Juhu/i)).toBeInTheDocument();
      });
    });
  });

  describe('NGOAdoptions Component', () => {
    it('renders applications inbox and provides approval action', async () => {
      const mockListings = [{ id: 'l-1', title: 'Bruno', species: 'Dog', status: 'PUBLISHED' }];
      const mockApps = [
        {
          id: 'app-99',
          status: 'SUBMITTED',
          applicant: {
            full_name: 'Rahul Varma',
            phone: '+919800000001',
            email: 'rahul@example.com',
          },
          listing: {
            title: 'Bruno',
          },
          housing_type: 'Independent House',
          has_fenced_garden: true,
          has_other_pets: false,
          family_members_count: 3,
          reason_for_adoption: 'Longtime dog lover seeking companion',
        },
      ];
      const mockEligible: any[] = [];

      (api.get as any).mockImplementation((url: string) => {
        if (url.includes('/ngo/adoptions/listings')) return Promise.resolve({ data: mockListings });
        if (url.includes('/ngo/adoptions/applications')) return Promise.resolve({ data: mockApps });
        if (url.includes('/ngo/adoptions/eligible-cases')) return Promise.resolve({ data: mockEligible });
        return Promise.resolve({ data: [] });
      });

      render(
        <MemoryRouter>
          <NGOAdoptions />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Adoption Operations')).toBeInTheDocument();
        expect(screen.getByText('Rahul Varma')).toBeInTheDocument();
        expect(screen.getByText('Approve & Finalize')).toBeInTheDocument();
      });

      // Click Approve & Finalize opens modal
      const approveBtn = screen.getByText('Approve & Finalize');
      fireEvent.click(approveBtn);

      await waitFor(() => {
        expect(screen.getByText(/Automatic Cascade Action/i)).toBeInTheDocument();
        expect(screen.getByText('Confirm Approval & Finalize')).toBeInTheDocument();
      });
    });
  });
});
