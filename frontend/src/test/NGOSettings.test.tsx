import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { NGOSettings } from '../pages/ngo/NGOSettings';
import api from '../services/api';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
  formatApiError: (err: any) => err?.message || 'Error',
}));

vi.mock('../context/useAuth', () => ({
  useAuth: () => ({
    logout: vi.fn(),
    user: { full_name: 'Admin User' },
  }),
}));

describe('NGOSettings Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders dispatch parameters and updates notification preferences', async () => {
    const mockDispatchSettings = {
      default_radius_km: 5.0,
      radius_escalation_levels: [5.0, 10.0, 20.0, 40.0],
      offer_expiration_seconds: 90,
      stale_location_timeout_seconds: 1800,
    };

    const mockPrefs = {
      critical_rescue_alerts: true,
      dispatch_failures: true,
      veterinary_updates: true,
      case_closures: true,
    };

    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/settings/dispatch')) return Promise.resolve({ data: mockDispatchSettings });
      if (url.includes('/me/preferences')) return Promise.resolve({ data: mockPrefs });
      return Promise.resolve({ data: {} });
    });

    (api.patch as any).mockResolvedValueOnce({
      data: {
        ...mockPrefs,
        dispatch_failures: false,
      },
    });

    render(<NGOSettings />);

    await waitFor(() => {
      expect(screen.getByText('Command Center Configuration')).toBeInTheDocument();
      expect(screen.getByText('90 seconds')).toBeInTheDocument();
      expect(screen.getByText('30 minutes')).toBeInTheDocument();
      expect(screen.getByText('Wave 1')).toBeInTheDocument();
      expect(screen.getByText('(40 km)')).toBeInTheDocument();
    });

    // Toggle dispatch failures checkbox
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]);

    const saveBtn = screen.getByRole('button', { name: /Save Alert Preferences/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/auth/me/preferences', expect.objectContaining({
        dispatch_failures: false,
      }));
      expect(screen.getByText(/Notification alert preferences saved successfully/i)).toBeInTheDocument();
    });
  });
});
