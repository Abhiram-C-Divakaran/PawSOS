import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { NotificationBell } from '../components/NotificationBell';
import api from '../services/api';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn(),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('NotificationBell Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders unread notification badge correctly', async () => {
    (api.get as any).mockResolvedValueOnce({
      data: {
        total: 2,
        unread_count: 2,
        items: [
          {
            id: 'notif-1',
            title: 'Critical Rescue Assigned',
            message: 'A critical dog rescue is within 2 km.',
            notification_type: 'DISPATCH_OFFER',
            is_read: false,
            created_at: new Date().toISOString(),
            data: { route: '/cases/case-123' },
          },
          {
            id: 'notif-2',
            title: 'Animal Arrived at Clinic',
            message: 'Dog #PR-001 has been admitted.',
            notification_type: 'AT_FACILITY',
            is_read: false,
            created_at: new Date().toISOString(),
          },
        ],
      },
    });

    render(
      <BrowserRouter>
        <NotificationBell />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument();
    });
  });

  it('opens notification tray on click and displays items', async () => {
    (api.get as any).mockResolvedValueOnce({
      data: {
        total: 1,
        unread_count: 1,
        items: [
          {
            id: 'notif-1',
            title: 'Critical Rescue Alert',
            message: 'Injured dog on 5th Ave',
            notification_type: 'DISPATCH_OFFER',
            is_read: false,
            created_at: new Date().toISOString(),
            data: { route: '/cases/case-123' },
          },
        ],
      },
    });

    render(
      <BrowserRouter>
        <NotificationBell />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /notifications/i }));

    expect(screen.getByText('Notifications')).toBeInTheDocument();
    expect(screen.getByText('Critical Rescue Alert')).toBeInTheDocument();
    expect(screen.getByText('Injured dog on 5th Ave')).toBeInTheDocument();
  });

  it('navigates and marks notification read when clicked', async () => {
    (api.get as any).mockResolvedValueOnce({
      data: {
        total: 1,
        unread_count: 1,
        items: [
          {
            id: 'notif-1',
            title: 'Case Assigned',
            message: 'Case PR-100 assigned',
            notification_type: 'RESPONDER_ASSIGNED',
            is_read: false,
            created_at: new Date().toISOString(),
            data: { route: '/cases/case-100' },
          },
        ],
      },
    });
    (api.patch as any).mockResolvedValueOnce({ data: { success: true } });

    render(
      <BrowserRouter>
        <NotificationBell />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /notifications/i }));
    fireEvent.click(screen.getByText('Case Assigned'));

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/notifications/notif-1/read');
      expect(mockNavigate).toHaveBeenCalledWith('/cases/case-100');
    });
  });

  it('marks all as read when Mark all read is clicked', async () => {
    (api.get as any).mockResolvedValueOnce({
      data: {
        total: 2,
        unread_count: 2,
        items: [
          {
            id: 'notif-1',
            title: 'Alert 1',
            message: 'Msg 1',
            is_read: false,
            created_at: new Date().toISOString(),
          },
          {
            id: 'notif-2',
            title: 'Alert 2',
            message: 'Msg 2',
            is_read: false,
            created_at: new Date().toISOString(),
          },
        ],
      },
    });
    (api.patch as any).mockResolvedValueOnce({ data: { success: true } });

    render(
      <BrowserRouter>
        <NotificationBell />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /notifications/i }));
    fireEvent.click(screen.getByText(/Mark all read/i));

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/notifications/read-all');
      expect(screen.queryByText('2')).not.toBeInTheDocument();
    });
  });
});
