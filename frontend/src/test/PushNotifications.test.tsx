import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { NotificationPermissionBanner } from '../components/NotificationPermissionBanner';
import { ForegroundNotificationToast } from '../components/ForegroundNotificationToast';
import * as firebaseService from '../services/firebase';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('Web Push Notifications & Foreground Alert Components', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('NotificationPermissionBanner Component', () => {
    it('renders banner when permission is default and not dismissed', () => {
      vi.stubGlobal('Notification', { permission: 'default' });

      render(<NotificationPermissionBanner />);

      expect(screen.getByTestId('notification-permission-banner')).toBeInTheDocument();
      expect(screen.getByText(/Enable Rescue Alerts/i)).toBeInTheDocument();
      expect(screen.getByTestId('enable-notifications-btn')).toHaveTextContent('Enable Alerts');
    });

    it('does not render if previously dismissed in localStorage', () => {
      vi.stubGlobal('Notification', { permission: 'default' });
      localStorage.setItem('pawreach_dismiss_push_banner', 'true');

      render(<NotificationPermissionBanner />);

      expect(screen.queryByTestId('notification-permission-banner')).not.toBeInTheDocument();
    });

    it('handles enabling notifications and registering token successfully', async () => {
      vi.stubGlobal('Notification', { permission: 'default' });

      const requestPermissionSpy = vi
        .spyOn(firebaseService, 'requestNotificationPermission')
        .mockResolvedValue('granted');
      const getTokenSpy = vi
        .spyOn(firebaseService, 'getFCMToken')
        .mockResolvedValue('test-fcm-token-12345');
      const registerSpy = vi
        .spyOn(firebaseService, 'registerDeviceTokenWithBackend')
        .mockResolvedValue(true);

      render(<NotificationPermissionBanner />);

      const enableBtn = screen.getByTestId('enable-notifications-btn');
      fireEvent.click(enableBtn);

      await waitFor(() => {
        expect(requestPermissionSpy).toHaveBeenCalled();
        expect(getTokenSpy).toHaveBeenCalled();
        expect(registerSpy).toHaveBeenCalledWith('test-fcm-token-12345');
      });
    });

    it('persists dismissal in localStorage when close button clicked', () => {
      vi.stubGlobal('Notification', { permission: 'default' });

      render(<NotificationPermissionBanner />);

      const dismissBtn = screen.getByTestId('dismiss-notifications-btn');
      fireEvent.click(dismissBtn);

      expect(localStorage.getItem('pawreach_dismiss_push_banner')).toBe('true');
      expect(screen.queryByTestId('notification-permission-banner')).not.toBeInTheDocument();
    });

    it('displays blocked indicator when permission is denied', () => {
      vi.stubGlobal('Notification', { permission: 'denied' });

      const onStatusChange = vi.fn();
      render(<NotificationPermissionBanner onStatusChange={onStatusChange} />);
      expect(onStatusChange).toHaveBeenCalledWith('denied');
    });
  });

  describe('ForegroundNotificationToast Component', () => {
    it('displays in-app toast when foreground notification arrives and navigates on click', async () => {
      let listenerCallback: ((payload: any) => void) | null = null;
      vi.spyOn(firebaseService, 'onForegroundNotification').mockImplementation((cb) => {
        listenerCallback = cb;
        return () => {};
      });

      render(
        <BrowserRouter>
          <ForegroundNotificationToast />
        </BrowserRouter>
      );

      expect(screen.queryByTestId('foreground-notification-toast')).not.toBeInTheDocument();
      expect(listenerCallback).not.toBeNull();

      act(() => {
        listenerCallback!({
          title: '🚨 CRITICAL: Dog Hit by Vehicle',
          body: 'Emergency rescue offer nearby! 1.2km away.',
          data: {
            case_id: 'case-abc-123',
            priority: 'CRITICAL',
          },
        });
      });

      await waitFor(() => {
        expect(screen.getByTestId('foreground-notification-toast')).toBeInTheDocument();
      });

      expect(screen.getByText('🚨 CRITICAL: Dog Hit by Vehicle')).toBeInTheDocument();
      expect(screen.getByText('Emergency rescue offer nearby! 1.2km away.')).toBeInTheDocument();

      const actionBtn = screen.getByTestId('toast-action-btn');
      fireEvent.click(actionBtn);

      expect(mockNavigate).toHaveBeenCalledWith('/cases/case-abc-123');
      expect(screen.queryByTestId('foreground-notification-toast')).not.toBeInTheDocument();
    });

    it('closes toast when user clicks dismiss button', async () => {
      let listenerCallback: ((payload: any) => void) | null = null;
      vi.spyOn(firebaseService, 'onForegroundNotification').mockImplementation((cb) => {
        listenerCallback = cb;
        return () => {};
      });

      render(
        <BrowserRouter>
          <ForegroundNotificationToast />
        </BrowserRouter>
      );

      act(() => {
        listenerCallback!({
          title: 'Rescue Update',
          body: 'Animal arrived at veterinary clinic.',
        });
      });

      await waitFor(() => {
        expect(screen.getByTestId('foreground-notification-toast')).toBeInTheDocument();
      });

      const closeBtn = screen.getByTestId('close-toast-btn');
      fireEvent.click(closeBtn);

      expect(screen.queryByTestId('foreground-notification-toast')).not.toBeInTheDocument();
    });
  });
});
