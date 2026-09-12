import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { NGOOrganization } from '../pages/ngo/NGOOrganization';
import api from '../services/api';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn(),
  },
  formatApiError: (err: any) => err?.message || 'Error',
}));

describe('NGOOrganization Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads profile and submits updates to authoritative backend', async () => {
    const mockProfile = {
      id: 'org-123',
      name: 'Kerala Animal Rescue Alliance',
      organization_type: 'NGO',
      phone: '+919847000000',
      operating_region: 'Kochi Central & Kakkanad',
      address: 'Panampilly Nagar, Kochi',
      description: 'Emergency response and triage ambulance fleet',
      responders_count: 12,
      veterinary_partners_count: 4,
      is_active: true,
    };

    (api.get as any).mockResolvedValueOnce({ data: mockProfile });
    (api.patch as any).mockResolvedValueOnce({
      data: {
        ...mockProfile,
        operating_region: 'Greater Kochi Metropolitan Area',
      },
    });

    render(<NGOOrganization />);

    await waitFor(() => {
      expect(screen.getByText('Kerala Animal Rescue Alliance')).toBeInTheDocument();
      expect(screen.getByText('12')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();
      expect(screen.getByText('Kochi Central & Kakkanad')).toBeInTheDocument();
    });

    // Update region input
    const regionInput = screen.getByLabelText(/Operating Region/i);
    fireEvent.change(regionInput, { target: { value: 'Greater Kochi Metropolitan Area' } });

    // Submit form
    const saveBtn = screen.getByRole('button', { name: /Save Changes/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/ngo/organization', expect.objectContaining({
        operating_region: 'Greater Kochi Metropolitan Area',
      }));
      expect(screen.getByText(/Organization profile updated and audited successfully/i)).toBeInTheDocument();
    });
  });
});
