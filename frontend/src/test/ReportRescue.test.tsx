import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ReportRescue } from '../pages/ReportRescue';

// Mock MapPicker to avoid Leaflet DOM container requirements in jsdom
vi.mock('../components/MapPicker', () => ({
  MapPicker: ({ onLocationSelect }: { onLocationSelect: (coords: { lat: number; lng: number }) => void }) => (
    <div data-testid="mock-map-picker">
      <button
        type="button"
        onClick={() => onLocationSelect({ lat: 19.076, lng: 72.8777 })}
      >
        Select Location
      </button>
    </div>
  ),
}));

// Mock API
vi.mock('../services/api', () => ({
  default: {
    post: vi.fn(),
  },
}));

describe('ReportRescue Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Step 1 with species selection options', () => {
    render(
      <BrowserRouter>
        <ReportRescue />
      </BrowserRouter>
    );

    expect(screen.getByText('What animal needs help?')).toBeInTheDocument();
    expect(screen.getByText('Dog')).toBeInTheDocument();
    expect(screen.getByText('Cat')).toBeInTheDocument();
    expect(screen.getByText('Cattle')).toBeInTheDocument();
    expect(screen.getByText('Bird')).toBeInTheDocument();
    expect(screen.getByText('Other')).toBeInTheDocument();
  });

  it('allows advancing to Step 2 (Photo Upload)', () => {
    render(
      <BrowserRouter>
        <ReportRescue />
      </BrowserRouter>
    );

    const continueBtn = screen.getByRole('button', { name: /Continue/i });
    fireEvent.click(continueBtn);

    expect(screen.getByText('Capture or Upload a Photo')).toBeInTheDocument();
    expect(screen.getByText(/JPG, PNG, or WEBP/i)).toBeInTheDocument();
  });

  it('allows navigating to Step 3 and requires location before advancing to Step 4', async () => {
    render(
      <BrowserRouter>
        <ReportRescue />
      </BrowserRouter>
    );

    // Step 1 -> Step 2
    fireEvent.click(screen.getByRole('button', { name: /Continue/i }));
    // Step 2 -> Step 3
    fireEvent.click(screen.getByRole('button', { name: /Continue/i }));

    expect(screen.getByText('Animal Location')).toBeInTheDocument();

    // Verify Continue button is disabled when location is null
    const continueBtn = screen.getByRole('button', { name: /Continue/i });
    expect(continueBtn).toBeDisabled();

    // Select location using mock map picker
    fireEvent.click(screen.getByText('Select Location'));
    expect(continueBtn).not.toBeDisabled();

    // Now click Continue -> advances to Step 4 (Triage)
    fireEvent.click(continueBtn);
    expect(screen.getByText('Visible Emergency Condition')).toBeInTheDocument();
  });

  it('toggles triage flags and allows entering description', async () => {
    render(
      <BrowserRouter>
        <ReportRescue />
      </BrowserRouter>
    );

    // Navigate to Step 3
    fireEvent.click(screen.getByRole('button', { name: /Continue/i }));
    fireEvent.click(screen.getByRole('button', { name: /Continue/i }));
    fireEvent.click(screen.getByText('Select Location'));
    fireEvent.click(screen.getByRole('button', { name: /Continue/i }));

    // Step 4: Triage
    expect(screen.getByText('Visible Emergency Condition')).toBeInTheDocument();
    expect(screen.getByText('Is the animal visibly bleeding?')).toBeInTheDocument();
    expect(screen.getByText('Hit by a vehicle or traffic collision?')).toBeInTheDocument();
    expect(screen.getByText('Does the animal have severe difficulty breathing?')).toBeInTheDocument();

    // Toggle bleeding checkbox
    const bleedingCheckbox = screen.getByLabelText(/Is the animal visibly bleeding/i);
    fireEvent.click(bleedingCheckbox);
    expect((bleedingCheckbox as HTMLInputElement).checked).toBe(true);

    // Fill notes
    const textarea = screen.getByPlaceholderText(/Specific animal markings/i);
    fireEvent.change(textarea, { target: { value: 'Dog is lying by the curb, bleeding from left paw' } });
    expect((textarea as HTMLTextAreaElement).value).toBe('Dog is lying by the curb, bleeding from left paw');
  });
});
