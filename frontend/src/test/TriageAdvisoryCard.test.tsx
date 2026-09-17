import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { TriageAdvisoryCard } from '../components/TriageAdvisoryCard';
import api from '../services/api';
import type { TriageDetailResponse } from '../types';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe('TriageAdvisoryCard Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    (api.get as any).mockReturnValue(new Promise(() => {})); // unresolved promise

    const { container } = render(<TriageAdvisoryCard caseId="test-case-123" />);
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  it('renders completed triage evaluation with detected signs and disclaimer', async () => {
    const mockTriage: TriageDetailResponse = {
      case_id: 'test-case-123',
      case_number: 'PR-2026-042',
      final_priority: 'CRITICAL',
      final_score: 90,
      final_reason: 'Visible bleeding reported, Active bleeding detected in left hind limb',
      rule_assessment: {
        priority: 'URGENT',
        score: 60,
        reasons: ['Visible bleeding reported'],
      },
      ai_assessment: {
        status: 'COMPLETED',
        source: 'HYBRID',
        suggested_priority: 'CRITICAL',
        score: 90,
        confidence: 0.88,
        visible_signs: ['Active bleeding detected', 'Significant tissue laceration'],
        explanation: 'Acute visual signs of trauma detected requiring urgent intervention.',
        provider: 'mock',
        model_name: 'pawreach-vision-safety',
        model_version: 'v1.0',
      },
      disclaimer:
        'AI visual triage provides decision-support for rescue dispatch urgency only. It does not constitute a veterinary medical diagnosis, injury assessment, or treatment prescription.',
    };

    (api.get as any).mockResolvedValueOnce({ data: mockTriage });

    render(<TriageAdvisoryCard caseId="test-case-123" />);

    await waitFor(() => {
      expect(screen.getByTestId('triage-advisory-card')).toBeInTheDocument();
    });

    // Check final priority badge
    expect(screen.getByTestId('final-priority-badge')).toHaveTextContent('CRITICAL (90/100)');

    // Check rule-based panel
    expect(screen.getByText(/Rule-Based Urgency/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Visible bleeding reported/i).length).toBeGreaterThanOrEqual(1);

    // Check AI visual advisory panel
    expect(screen.getByText(/Evaluated/i)).toBeInTheDocument();
    expect(screen.getByText(/88% confidence/i)).toBeInTheDocument();
    expect(screen.getByText('Active bleeding detected')).toBeInTheDocument();
    expect(screen.getByText('Significant tissue laceration')).toBeInTheDocument();

    // Check prominent safety & non-diagnostic notice
    expect(screen.getByText(/Safety & Legal Notice:/i)).toBeInTheDocument();
    expect(screen.getByText(/It does not constitute a veterinary medical diagnosis/i)).toBeInTheDocument();
  });

  it('renders pending advisory when visual analysis is queued', async () => {
    const mockTriage: TriageDetailResponse = {
      case_id: 'test-case-456',
      case_number: 'PR-2026-099',
      final_priority: 'GENERAL',
      final_score: 20,
      final_reason: 'Standard rescue protocol',
      rule_assessment: {
        priority: 'GENERAL',
        score: 20,
        reasons: [],
      },
      ai_assessment: {
        status: 'PENDING',
        source: 'IMAGE_AI',
        provider: 'mock',
        model_name: 'pawreach-vision-safety',
        model_version: 'v1.0',
      },
      disclaimer: 'AI visual triage provides decision-support for rescue dispatch urgency only.',
    };

    (api.get as any).mockResolvedValueOnce({ data: mockTriage });

    render(<TriageAdvisoryCard caseId="test-case-456" />);

    await waitFor(() => {
      expect(screen.getByText(/Analyzing attached image for visible trauma signs/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Pending/i)).toBeInTheDocument();
  });

  it('renders skipped state when AI triage is inactive', async () => {
    const mockTriage: TriageDetailResponse = {
      case_id: 'test-case-789',
      case_number: 'PR-2026-100',
      final_priority: 'URGENT',
      final_score: 50,
      final_reason: 'Vehicle collision reported',
      rule_assessment: {
        priority: 'URGENT',
        score: 50,
        reasons: ['Vehicle collision reported'],
      },
      ai_assessment: {
        status: 'SKIPPED',
        source: 'RULES',
        explanation: 'Visual triage is disabled in configuration.',
      },
      disclaimer: 'Decision-support only.',
    };

    (api.get as any).mockResolvedValueOnce({ data: mockTriage });

    render(<TriageAdvisoryCard caseId="test-case-789" />);

    await waitFor(() => {
      expect(screen.getByText(/Visual triage is disabled in configuration/i)).toBeInTheDocument();
    });
  });

  it('supports retry action for authorized operators', async () => {
    const mockTriage: TriageDetailResponse = {
      case_id: 'test-case-retry',
      case_number: 'PR-2026-200',
      final_priority: 'MODERATE',
      final_score: 30,
      final_reason: 'Animal unable to walk',
      rule_assessment: {
        priority: 'MODERATE',
        score: 30,
        reasons: ['Animal unable to walk'],
      },
      ai_assessment: {
        status: 'FAILED',
        source: 'IMAGE_AI',
        explanation: 'Visual assessment service temporarily unavailable.',
      },
      disclaimer: 'Decision-support only.',
    };

    (api.get as any).mockResolvedValue({ data: mockTriage });
    (api.post as any).mockResolvedValueOnce({
      data: { success: true, message: 'Visual triage assessment queued for execution.' },
    });

    render(<TriageAdvisoryCard caseId="test-case-retry" canRetry={true} />);

    await waitFor(() => {
      expect(screen.getByTitle(/Re-run visual triage assessment/i)).toBeInTheDocument();
    });

    const retryBtn = screen.getByTitle(/Re-run visual triage assessment/i);
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/rescues/test-case-retry/triage/retry?force=true');
      expect(screen.getByText(/Visual triage assessment queued for execution/i)).toBeInTheDocument();
    });
  });

  it('renders disabled / not requested state without active analyzing animation when AI is disabled', async () => {
    const mockTriage: TriageDetailResponse = {
      case_id: 'test-case-disabled',
      case_number: 'PR-2026-300',
      final_priority: 'MODERATE',
      final_score: 30,
      final_reason: 'Reported symptoms',
      rule_assessment: {
        priority: 'MODERATE',
        score: 30,
        reasons: ['Reported symptoms'],
      },
      ai_assessment: {
        status: 'NOT_REQUESTED',
        source: 'IMAGE_AI',
        provider: 'disabled',
        explanation: 'Visual AI triage is disabled in system configuration.',
      },
      disclaimer: 'Decision-support only.',
    };

    (api.get as any).mockResolvedValueOnce({ data: mockTriage });

    render(<TriageAdvisoryCard caseId="test-case-disabled" />);

    await waitFor(() => {
      expect(screen.getByText(/Visual AI triage is disabled in system configuration/i)).toBeInTheDocument();
    });

    expect(screen.getByText('Disabled')).toBeInTheDocument();
    expect(screen.queryByText(/Analyzing attached image/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Pending/i)).not.toBeInTheDocument();
  });
});

