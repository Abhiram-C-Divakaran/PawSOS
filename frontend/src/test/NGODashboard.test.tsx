import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { NGOOverview } from '../pages/ngo/NGOOverview';
import { NGOCases } from '../pages/ngo/NGOCases';
import { NGOResponders } from '../pages/ngo/NGOResponders';
import api from '../services/api';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

// Mock leaflet for NGOOverview map
vi.mock('leaflet', () => ({
  default: {
    map: vi.fn(() => ({
      setView: vi.fn().mockReturnThis(),
      remove: vi.fn(),
    })),
    tileLayer: vi.fn(() => ({
      addTo: vi.fn().mockReturnThis(),
    })),
    marker: vi.fn(() => ({
      addTo: vi.fn().mockReturnThis(),
      on: vi.fn().mockReturnThis(),
    })),
    divIcon: vi.fn(() => ({})),
    circle: vi.fn(() => ({
      addTo: vi.fn().mockReturnThis(),
    })),
  },
}));

describe('NGO Operations Command Center Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('NGOOverview', () => {
    it('renders real operational KPIs and hotspot summary', async () => {
      const mockKPIs = {
        active_cases: 14,
        critical_cases: 3,
        awaiting_responder: 4,
        responders_en_route: 2,
        under_treatment: 5,
        recovering: 8,
        avg_dispatch_seconds: 42.5,
        avg_response_minutes: 16.2,
        completion_rate_pct: 91.5,
        responder_availability_pct: 75.0,
        total_cases: 20,
      };

      const mockHotspots = [
        {
          latitude: 19.06,
          longitude: 72.83,
          area_name: 'Bandra West (19.06, 72.83)',
          incident_count: 8,
          critical_count: 2,
          top_species: 'Dog',
        },
      ];

      (api.get as any).mockImplementation((url: string) => {
        if (url.includes('/analytics/overview')) {
          return Promise.resolve({ data: mockKPIs });
        }
        if (url.includes('/analytics/hotspots')) {
          return Promise.resolve({ data: mockHotspots });
        }
        if (url.includes('/cases')) {
          return Promise.resolve({ data: [] });
        }
        return Promise.resolve({ data: {} });
      });

      render(
        <BrowserRouter>
          <NGOOverview />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('14')).toBeInTheDocument();
        expect(screen.getByText('42.5s')).toBeInTheDocument();
        expect(screen.getByText('16.2 min')).toBeInTheDocument();
        expect(screen.getByText('91.5%')).toBeInTheDocument();
      });

      expect(screen.getByText('Bandra West (19.06, 72.83)')).toBeInTheDocument();
      expect(screen.getByText('8 reports')).toBeInTheDocument();
    });
  });

  describe('NGOCases', () => {
    it('renders cases list and supports priority filtering', async () => {
      const mockCases = [
        {
          id: 'c-1',
          case_number: 'PR-2026-001',
          species: 'Cat',
          triage_priority: 'CRITICAL',
          status: 'SEARCHING_RESPONDER',
          address_text: 'Colaba Causeway',
          created_at: new Date().toISOString(),
        },
        {
          id: 'c-2',
          case_number: 'PR-2026-002',
          species: 'Dog',
          triage_priority: 'MODERATE',
          status: 'CLOSED',
          address_text: 'Andheri East',
          created_at: new Date().toISOString(),
        },
      ];

      (api.get as any).mockResolvedValueOnce({ data: mockCases });

      render(
        <BrowserRouter>
          <NGOCases />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('PR-2026-001')).toBeInTheDocument();
        expect(screen.getByText('PR-2026-002')).toBeInTheDocument();
      });

      expect(screen.getByText('Colaba Causeway')).toBeInTheDocument();
      expect(screen.getByText('Andheri East')).toBeInTheDocument();

      // Trigger priority filter change
      (api.get as any).mockResolvedValueOnce({
        data: [mockCases[0]],
      });

      const selects = screen.getAllByRole('combobox');
      fireEvent.change(selects[0], { target: { value: 'CRITICAL' } });

      await waitFor(() => {
        expect(api.get).toHaveBeenCalledWith('/ngo/cases', expect.objectContaining({
          params: expect.objectContaining({ priority: 'CRITICAL' }),
        }));
      });
    });
  });

  describe('NGOResponders', () => {
    it('renders responder roster and toggles active status', async () => {
      const mockResponders = [
        {
          id: 'p-1',
          user_id: 'u-1',
          full_name: 'Anita Sharma',
          email: 'anita@example.com',
          phone: '+919876543210',
          is_active: true,
          availability_status: 'AVAILABLE',
          vehicle_available: true,
          experience_level: 'Advanced',
          reliability_score: 95.0,
          completed_rescues: 18,
          total_offers: 20,
          accepted_offers: 19,
          acceptance_rate_pct: 95.0,
        },
      ];

      (api.get as any).mockResolvedValueOnce({ data: mockResponders });
      (api.patch as any).mockResolvedValueOnce({ data: { success: true } });

      render(
        <BrowserRouter>
          <NGOResponders />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Anita Sharma')).toBeInTheDocument();
        expect(screen.getByText('anita@example.com')).toBeInTheDocument();
        expect(screen.getByText('AVAILABLE')).toBeInTheDocument();
        expect(screen.getAllByText('95%').length).toBeGreaterThanOrEqual(1);
      });

      const toggleBtn = screen.getByRole('button', { name: /Deactivate/i });
      fireEvent.click(toggleBtn);

      await waitFor(() => {
        expect(api.patch).toHaveBeenCalledWith('/ngo/responders/u-1/status', {
          is_active: false,
        });
      });
    });
  });
});
