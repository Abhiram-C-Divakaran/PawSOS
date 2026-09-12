import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { RescuerDashboard } from '../pages/RescuerDashboard';
import api from '../services/api';

vi.mock('../components/MapView', () => ({
  MapView: () => <div data-testid="mock-map-view">Mock Map View</div>,
}));

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

describe('RescuerDashboard - Dispatch Offers Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock geolocation
    const mockGeolocation = {
      getCurrentPosition: vi.fn((success) =>
        success({
          coords: {
            latitude: 19.076,
            longitude: 72.8777,
          },
        })
      ),
      watchPosition: vi.fn(),
    };
    (global as any).navigator.geolocation = mockGeolocation;
  });

  const mockOffers = [
    {
      id: 'offer-1',
      rescue_case_id: 'case-999',
      rescuer_id: 'rescuer-me',
      assignment_status: 'PENDING',
      distance_km: 1.4,
      dispatch_score: 92.5,
      offered_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 85000).toISOString(),
      case: {
        id: 'case-999',
        case_number: 'PR-2026-999',
        species: 'Dog',
        triage_priority: 'CRITICAL',
        description: 'Dog hit by vehicle, severe bleeding',
        address_text: 'SV Road, Bandra West',
        latitude: 19.078,
        longitude: 72.879,
      },
    },
  ];

  it('renders incoming dispatch offers with countdown timer and match score', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/rescuers/me/offers')) {
        return Promise.resolve({ data: mockOffers });
      }
      if (url.includes('/facilities')) {
        return Promise.resolve({ data: [] });
      }
      if (url.includes('/rescues/nearby')) {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: {} });
    });
    (api.patch as any).mockResolvedValue({ data: { success: true } });

    render(
      <BrowserRouter>
        <RescuerDashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Incoming Rescue Alerts/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/CRITICAL ALERT/i)).toBeInTheDocument();
    expect(screen.getByText(/Dog hit by vehicle, severe bleeding/i)).toBeInTheDocument();
    expect(screen.getByText('1.4 km away')).toBeInTheDocument();
    expect(screen.getByText('92.5%')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Accept Rescue/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Decline/i })).toBeInTheDocument();
  });

  it('accepts incoming dispatch offer via POST /rescuers/offers/{id}/accept', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/rescuers/me/offers')) {
        return Promise.resolve({ data: mockOffers });
      }
      if (url.includes('/facilities')) {
        return Promise.resolve({ data: [] });
      }
      if (url.includes('/rescues/nearby')) {
        return Promise.resolve({ data: [] });
      }
      if (url.includes('/rescues/case-999')) {
        return Promise.resolve({
          data: {
            id: 'case-999',
            case_number: 'PR-2026-999',
            species: 'Dog',
            status: 'RESPONDER_ASSIGNED',
            triage_priority: 'CRITICAL',
            latitude: 19.078,
            longitude: 72.879,
            address_text: 'SV Road, Bandra West',
            description: 'Dog hit by vehicle',
          },
        });
      }
      return Promise.resolve({ data: {} });
    });
    (api.patch as any).mockResolvedValue({ data: { success: true } });
    (api.post as any).mockResolvedValue({
      data: {
        success: true,
        assignment_id: 'offer-1',
        rescue_case_id: 'case-999',
      },
    });

    render(
      <BrowserRouter>
        <RescuerDashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Accept Rescue/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Accept Rescue/i }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/rescuers/offers/offer-1/accept');
    });
  });

  it('declines offer with selected reason via POST /rescuers/offers/{id}/reject', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/rescuers/me/offers')) {
        return Promise.resolve({ data: mockOffers });
      }
      if (url.includes('/facilities')) {
        return Promise.resolve({ data: [] });
      }
      if (url.includes('/rescues/nearby')) {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: {} });
    });
    (api.patch as any).mockResolvedValue({ data: { success: true } });
    (api.post as any).mockResolvedValue({ data: { success: true } });

    render(
      <BrowserRouter>
        <RescuerDashboard />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Decline/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Decline/i }));

    // Decline modal opens
    expect(screen.getByText('Decline Rescue Offer')).toBeInTheDocument();

    // Select reason radio button
    fireEvent.click(screen.getByLabelText(/Vehicle or transport unavailable/i));

    // Confirm decline
    fireEvent.click(screen.getByRole('button', { name: /Confirm Decline/i }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/rescuers/offers/offer-1/reject', {
        reason: 'vehicle_unavailable',
      });
    });
  });
});
