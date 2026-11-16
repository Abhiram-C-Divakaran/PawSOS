import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, X, ChevronRight, ShieldAlert } from 'lucide-react';
import { onForegroundNotification, sanitizeNotificationRoute } from '../services/firebase';

interface ToastData {
  id: string;
  title: string;
  body: string;
  route?: string;
  priority?: string;
}

export const ForegroundNotificationToast: React.FC = () => {
  const [activeToast, setActiveToast] = useState<ToastData | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const unsubscribe = onForegroundNotification((payload) => {
      const route = sanitizeNotificationRoute(payload.data?.route, payload.data?.case_id);
      const priority = payload.data?.priority || (payload.title?.includes('CRITICAL') ? 'CRITICAL' : 'GENERAL');
      const toast: ToastData = {
        id: Date.now().toString(),
        title: payload.title || '🚨 Emergency Rescue Alert',
        body: payload.body || 'New rescue dispatch update received.',
        route,
        priority,
      };
      setActiveToast(toast);

      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      timerRef.current = setTimeout(() => {
        setActiveToast((current) => (current?.id === toast.id ? null : current));
      }, 10000);
    });

    return () => {
      unsubscribe();
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  if (!activeToast) return null;

  const handleClick = () => {
    if (activeToast.route) {
      navigate(activeToast.route);
    }
    setActiveToast(null);
  };

  const isCritical = activeToast.priority === 'CRITICAL' || activeToast.title.includes('CRITICAL');

  return (
    <div
      id="foreground-notification-toast"
      data-testid="foreground-notification-toast"
      role="alert"
      aria-live={isCritical ? 'assertive' : 'polite'}
      className="fixed top-20 right-4 left-4 sm:left-auto z-50 max-w-md sm:w-full animate-slide-in-down"
    >
      <div
        className={`rounded-xl p-4 shadow-2xl border backdrop-blur-md transition-all flex items-start gap-3.5 ${
          isCritical
            ? 'bg-red-950/95 border-red-500/50 text-red-100 ring-2 ring-red-500/30'
            : 'bg-stone-900/95 border-amber-500/40 text-stone-100 ring-2 ring-amber-500/20'
        }`}
      >
        <div
          className={`p-2 rounded-lg shrink-0 ${
            isCritical ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400'
          }`}
        >
          {isCritical ? (
            <ShieldAlert className="w-5 h-5 animate-pulse" />
          ) : (
            <AlertTriangle className="w-5 h-5" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-1">
            <h4 className="font-bold text-sm truncate text-white">{activeToast.title}</h4>
            <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-white/10 shrink-0">
              Now
            </span>
          </div>
          <p className="text-xs text-stone-300 mt-1 line-clamp-2 leading-relaxed">
            {activeToast.body}
          </p>
          {activeToast.route && (
            <button
              id="toast-action-btn"
              data-testid="toast-action-btn"
              type="button"
              onClick={handleClick}
              className="mt-2.5 inline-flex items-center gap-1 text-xs font-bold text-amber-400 hover:text-amber-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 rounded transition-colors"
            >
              View Rescue <ChevronRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <button
          id="close-toast-btn"
          data-testid="close-toast-btn"
          type="button"
          onClick={() => setActiveToast(null)}
          aria-label="Close notification"
          className="text-stone-400 hover:text-white p-1 rounded-md hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-white shrink-0 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
