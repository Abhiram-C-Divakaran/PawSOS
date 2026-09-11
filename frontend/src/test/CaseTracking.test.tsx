import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { CaseTracking } from '../pages/CaseTracking';
import api from '../services/api';

// Mock MapView
vi.mock('../components/MapView', () => ({
  MapView: () => <div data-testid="mock-map-view">Mock Map View</div>,
}));

// Mock API
vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

describe('CaseTracking Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    (api.get as any).mockReturnValue(new Promise(() => {})); // pending promise

    render(
      <BrowserRouter>
        <CaseTracking />
      </BrowserRouter>
    );

    expect(screen.getByText(/Fetching real-time case data/i)).toBeInTheDocument();
  });

  it('renders case details and timeline on successful fetch', async () => {
    const mockCase = {
      id: 'case-123',
      species: 'Dog',
      status: 'RESPONDER_EN_ROUTE',
      triage_priority: 'CRITICAL',
      triage_score: 85,
      latitude: 19.076,
      longitude: 72.8777,
      address_text: 'Linking Road, Bandra',
      description: 'Injured street dog',
      images: [
        {
          id: 'img-1',
          image_url: '/uploads/dog_rescue.jpg',
          is_primary: true,
        },
      ],
      assigned_responder: {
        id: 'rescuer-1',
        full_name: 'Anita Sharma',
        phone: '+919876543210',
      },
      case_number: 'PR-2026-001',
      created_at: '2026-09-11T10:00:00Z',
    };

    const mockTimeline = [
      {
        id: 't-1',
        rescue_case_id: 'case-123',
        previous_status: 'REPORTED',
        new_status: 'TRIAGED',
        notes: 'Auto-triaged',
        created_at: '2026-09-11T10:00:01Z',
      },
      {
        id: 't-2',
        rescue_case_id: 'case-123',
        previous_status: 'TRIAGED',
        new_status: 'RESPONDER_ASSIGNED',
        notes: 'Accepted by Anita Sharma',
        created_at: '2026-09-11T10:05:00Z',
      },
      {
        id: 't-3',
        rescue_case_id: 'case-123',
        previous_status: 'RESPONDER_ASSIGNED',
        new_status: 'RESPONDER_EN_ROUTE',
        notes: 'En route',
        created_at: '2026-09-11T10:06:00Z',
      },
    ];

    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/timeline')) {
        return Promise.resolve({ data: mockTimeline });
      }
      return Promise.resolve({ data: mockCase });
    });

    render(
      <BrowserRouter>
        <CaseTracking />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Case PR-2026-001')).toBeInTheDocument();
    });

    expect(screen.getByText('CRITICAL PRIORITY')).toBeInTheDocument();
    expect(screen.getByText('Dog')).toBeInTheDocument();
    expect(screen.getByText('Linking Road, Bandra')).toBeInTheDocument();
    expect(screen.getByText('Anita Sharma')).toBeInTheDocument();
    expect(screen.getByText('Mock Map View')).toBeInTheDocument();
  });

  it('renders restricted access UI on 403 / error', async () => {
    (api.get as any).mockRejectedValue({
      response: {
        data: {
          detail: 'You do not have permission to access this rescue case.',
        },
      },
    });

    render(
      <BrowserRouter>
        <CaseTracking />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Access Restricted')).toBeInTheDocument();
    });

    expect(screen.getByText(/You do not have permission to access this rescue case/i)).toBeInTheDocument();
  });
});
