import React, { useState, useEffect } from 'react';
import { Bell, X, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { requestNotificationPermission, getFCMToken, registerDeviceTokenWithBackend } from '../services/firebase';

interface Props {
  onStatusChange?: (status: string) => void;
}

export const NotificationPermissionBanner: React.FC<Props> = ({ onStatusChange }) => {
  const [isVisible, setIsVisible] = useState<boolean>(false);
  const [status, setStatus] = useState<string>('default');
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      setStatus('unsupported');
      onStatusChange?.('unsupported');
      return;
    }

    const perm = Notification.permission;
    setStatus(perm);
    onStatusChange?.(perm);

    const dismissed = localStorage.getItem('pawreach_dismiss_push_banner') === 'true';
    if (perm === 'default' && !dismissed) {
      setIsVisible(true);
    }
  }, [onStatusChange]);

  const handleEnable = async () => {
    setLoading(true);
    try {
      const result = await requestNotificationPermission();
      setStatus(result);
      onStatusChange?.(result);

      if (result === 'granted') {
        const token = await getFCMToken();
        if (token) {
          await registerDeviceTokenWithBackend(token);
        }
        setIsVisible(false);
      } else if (result === 'denied') {
        // Hide after showing denied state
        setTimeout(() => setIsVisible(false), 3000);
      }
    } catch (err) {
      console.error('Permission request failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDismiss = () => {
    localStorage.setItem('pawreach_dismiss_push_banner', 'true');
    setIsVisible(false);
  };

  if (!isVisible) return null;

  return (
    <div
      id="notification-permission-banner"
      data-testid="notification-permission-banner"
      className="bg-gradient-to-r from-amber-900/90 to-amber-950/95 border-b border-amber-500/30 text-white px-4 py-3 shadow-lg z-40 transition-all"
    >
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-amber-500/20 rounded-lg text-amber-400 shrink-0">
            <Bell className="w-5 h-5 animate-bounce" />
          </div>
          <div>
            <p className="font-semibold text-sm sm:text-base flex items-center gap-2">
              Enable Rescue Alerts
              {status === 'denied' && (
                <span className="inline-flex items-center gap-1 text-xs text-red-400 bg-red-950/80 px-2 py-0.5 rounded-full border border-red-500/30">
                  <ShieldAlert className="w-3 h-3" /> Blocked in browser settings
                </span>
              )}
              {status === 'granted' && (
                <span className="inline-flex items-center gap-1 text-xs text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded-full border border-emerald-500/30">
                  <CheckCircle2 className="w-3 h-3" /> Enabled
                </span>
              )}
            </p>
            <p className="text-xs sm:text-sm text-stone-300">
              Receive urgent dispatch offers, rescue progress, and case updates even when PawReach is not open.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            id="enable-notifications-btn"
            data-testid="enable-notifications-btn"
            onClick={handleEnable}
            disabled={loading || status === 'denied'}
            className="px-4 py-2 text-xs sm:text-sm font-semibold rounded-lg bg-amber-500 hover:bg-amber-400 text-stone-950 disabled:opacity-50 transition-colors shadow"
          >
            {loading ? 'Activating...' : status === 'denied' ? 'Permission Denied' : 'Enable Alerts'}
          </button>
          <button
            id="dismiss-notifications-btn"
            data-testid="dismiss-notifications-btn"
            onClick={handleDismiss}
            aria-label="Dismiss banner"
            className="p-2 text-stone-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
