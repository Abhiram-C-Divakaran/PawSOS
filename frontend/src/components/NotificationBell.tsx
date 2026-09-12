import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCheck, ShieldAlert, HeartHandshake, Stethoscope } from 'lucide-react';
import api from '../services/api';
import type { NotificationItem } from '../types';

interface NotificationBellProps {
  variant?: 'light' | 'dark';
  className?: string;
}

export const NotificationBell: React.FC<NotificationBellProps> = ({ variant = 'light', className = '' }) => {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await api.get('/notifications');
      setNotifications(res.data.items || []);
      setUnreadCount(res.data.unread_count || 0);
    } catch {
      // Ignore network errors in polling
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 15000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleMarkAllRead = async () => {
    try {
      await api.patch('/notifications/read-all');
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error('Failed to mark all as read', err);
    }
  };

  const handleNotificationClick = async (notif: NotificationItem) => {
    if (!notif.is_read) {
      try {
        await api.patch(`/notifications/${notif.id}/read`);
        setNotifications((prev) =>
          prev.map((n) => (n.id === notif.id ? { ...n, is_read: true } : n))
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      } catch {
        // Continue navigation even if read patch fails
      }
    }

    setIsOpen(false);

    if (notif.data) {
      try {
        const parsed = typeof notif.data === 'string' ? JSON.parse(notif.data) : notif.data;
        if (parsed?.route) {
          navigate(parsed.route);
          return;
        } else if (parsed?.case_id) {
          navigate(`/cases/${parsed.case_id}`);
          return;
        }
      } catch {
        // ignore parse errors
      }
    }
    if (notif.rescue_case_id) {
      navigate(`/cases/${notif.rescue_case_id}`);
    }
  };

  const getEventIcon = (type?: string) => {
    if (!type) {
      return <HeartHandshake className="w-4 h-4 text-emerald-500" />;
    }
    if (type.includes('CRITICAL') || type.includes('DISPATCH')) {
      return <ShieldAlert className="w-4 h-4 text-red-500" />;
    }
    if (type.includes('VET') || type.includes('TREATMENT') || type.includes('FACILITY')) {
      return <Stethoscope className="w-4 h-4 text-purple-500" />;
    }
    return <HeartHandshake className="w-4 h-4 text-emerald-500" />;
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        id="notification-bell-btn"
        aria-label="View notifications"
        onClick={() => setIsOpen(!isOpen)}
        className={`relative p-2.5 rounded-full transition-all focus:outline-none ${
          variant === 'dark'
            ? 'text-gray-300 hover:text-white hover:bg-white/10'
            : 'text-slate-600 hover:text-slate-900 bg-slate-100/70 hover:bg-slate-200/70 border border-slate-200'
        } ${className}`}
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span
            id="notification-badge"
            className="absolute top-1 right-1 flex items-center justify-center min-w-[1.125rem] h-4.5 px-1 text-[10px] font-bold text-white bg-red-600 rounded-full ring-2 ring-white animate-pulse"
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          id="notification-dropdown"
          className="absolute right-0 mt-2 w-80 sm:w-96 bg-white rounded-xl shadow-2xl border border-slate-200 z-50 overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-200">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-900 text-sm">Notifications</span>
              {unreadCount > 0 && (
                <span className="px-1.5 py-0.5 text-xs font-semibold bg-blue-100 text-blue-800 rounded-full">
                  {unreadCount} new
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="flex items-center gap-1 text-xs text-slate-600 hover:text-blue-700 font-medium transition-colors"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                Mark all read
              </button>
            )}
          </div>

          {/* List */}
          <div className="max-h-80 overflow-y-auto divide-y divide-stone-100">
            {notifications.length === 0 ? (
              <div className="py-8 text-center text-stone-400 text-sm">
                No notifications right now
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  onClick={() => handleNotificationClick(n)}
                  className={`px-4 py-3 cursor-pointer hover:bg-blue-50/50 transition-colors flex items-start gap-3 ${
                    !n.is_read ? 'bg-blue-50/30 font-medium' : 'text-slate-700'
                  }`}
                >
                  <div className="mt-0.5 p-1 rounded-full bg-slate-100">
                    {getEventIcon(n.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline justify-between gap-1">
                      <p className="text-xs font-bold text-stone-900 truncate">{n.title}</p>
                      <span className="text-[10px] text-stone-400 shrink-0">
                        {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <p className="text-xs text-stone-600 mt-0.5 line-clamp-2 leading-snug">{n.message}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
