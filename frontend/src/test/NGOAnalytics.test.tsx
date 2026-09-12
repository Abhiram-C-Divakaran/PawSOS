import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { NGOAnalytics } from '../pages/ngo/NGOAnalytics';
import api from '../services/api';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

// Mock Recharts ResponsiveContainer to render in test DOM
vi.mock('recharts', async () => {
  const original = await vi.importActual<any>('recharts');
  return {
    ...original,
    ResponsiveContainer: ({ children }: any) => <div style={{ width: 500, height: 300 }}>{children}</div>,
  };
});

describe('NGOAnalytics Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders analytics KPI row, period filters, and outcome breakdown', async () => {
    const mockOverview = {
      total_cases: 45,
      average_response_minutes: 14.8,
      completion_rate_pct: 93.3,
    };
    const mockOutcomes = {
      outcomes: { RESCUED: 30, CLOSED: 10, UNRESOLVED: 2 },
      rescue_success_rate: 88.9,
      unresolved_rate: 4.4,
      veterinary_handoff_rate: 66.7,
      total_cases: 45,
    };
    const mockInsights = {
      busiest_day: 'Saturday',
      busiest_time_range: '14:00 - 18:00',
      responder_acceptance_rate_pct: 92.5,
      avg_dispatch_attempts: 1.2,
      escalation_rate_pct: 12.0,
    };
    const mockHotspots = [
      {
        area_name: 'Marine Drive Zone',
        incident_count: 15,
        critical_count: 4,
        top_species: 'Dog',
        average_response_minutes: 12.5,
      },
    ];

    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/analytics/overview')) return Promise.resolve({ data: mockOverview });
      if (url.includes('/analytics/outcomes')) return Promise.resolve({ data: mockOutcomes });
      if (url.includes('/analytics/insights')) return Promise.resolve({ data: mockInsights });
      if (url.includes('/analytics/hotspots')) return Promise.resolve({ data: mockHotspots });
      if (url.includes('/analytics/response-times')) return Promise.resolve({ data: [] });
      return Promise.resolve({ data: {} });
    });

    render(
      <BrowserRouter>
        <NGOAnalytics />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Operations & Impact Analytics')).toBeInTheDocument();
      expect(screen.getByText('45')).toBeInTheDocument();
      expect(screen.getByText('14.8')).toBeInTheDocument();
      expect(screen.getByText('88.9')).toBeInTheDocument();
      expect(screen.getByText('92.5')).toBeInTheDocument();
    });

    expect(screen.getByText('Saturday')).toBeInTheDocument();
    expect(screen.getByText('14:00 - 18:00')).toBeInTheDocument();
    expect(screen.getByText('Marine Drive Zone')).toBeInTheDocument();

    // Test period switch
    const days7Btn = screen.getByRole('button', { name: '7 Days' });
    fireEvent.click(days7Btn);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/ngo/analytics/response-times?period=7d');
    });
  });
});
