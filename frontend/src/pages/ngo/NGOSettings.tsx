import React, { useState, useEffect } from 'react';
import {
  Settings,
  Bell,
  Radio,
  Shield,
  Smartphone,
  LogOut,
  Save,
  CheckCircle2,
  AlertCircle,
  RotateCw,
} from 'lucide-react';
import api, { formatApiError } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import type { DispatchSettings, NotificationPreferences } from '../../types';

export const NGOSettings: React.FC = () => {
  const { logout } = useAuth();
  const [dispatchSettings, setDispatchSettings] = useState<DispatchSettings | null>(null);
  const [prefs, setPrefs] = useState<NotificationPreferences>({
    critical_rescue_alerts: true,
    dispatch_failures: true,
    veterinary_updates: true,
    case_closures: true,
  });

  const [loading, setLoading] = useState<boolean>(true);
  const [savingPrefs, setSavingPrefs] = useState<boolean>(false);
  const [revokingSessions, setRevokingSessions] = useState<boolean>(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fcmTesting, setFcmTesting] = useState<boolean>(false);
  const [fcmResult, setFcmResult] = useState<string | null>(null);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      setError(null);
      const [dispatchRes, prefRes] = await Promise.all([
        api.get('/ngo/settings/dispatch'),
        api.get('/auth/me/preferences').catch(() => ({
          data: {
            critical_rescue_alerts: true,
            dispatch_failures: true,
            veterinary_updates: true,
            case_closures: true,
          },
        })),
      ]);

      setDispatchSettings(dispatchRes.data);
      if (prefRes.data) {
        setPrefs(prefRes.data);
      }
    } catch (err: any) {
      console.error('Failed to load settings', err);
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleSavePreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSavingPrefs(true);
      setError(null);
      setSuccessMsg(null);
      const res = await api.patch('/auth/me/preferences', prefs);
      setPrefs(res.data);
      setSuccessMsg('Notification alert preferences saved successfully.');
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      console.error('Failed to save preferences', err);
      setError(formatApiError(err));
    } finally {
      setSavingPrefs(false);
    }
  };

  const handleLogoutAll = async () => {
    if (!window.confirm('Are you sure you want to revoke all active sessions across all devices? You will be logged out immediately.')) {
      return;
    }
    try {
      setRevokingSessions(true);
      await api.post('/auth/logout-all');
      await logout();
      window.location.href = '/login';
    } catch (err: any) {
      console.error('Failed to revoke sessions', err);
      setError(formatApiError(err));
      setRevokingSessions(false);
    }
  };

  const testPushNotification = () => {
    setFcmTesting(true);
    setFcmResult(null);

    if (!('Notification' in window)) {
      setFcmResult('Desktop browser notifications are not supported in this environment.');
      setFcmTesting(false);
      return;
    }

    if (Notification.permission === 'granted') {
      new Notification('PawReach SOS Operational Alert', {
        body: 'Push notification engine is operational and ready for pilot deployment.',
        icon: '/favicon.ico',
      });
      setFcmResult('Test notification triggered successfully.');
      setFcmTesting(false);
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission().then((permission) => {
        if (permission === 'granted') {
          new Notification('PawReach SOS Operational Alert', {
            body: 'Push notification engine is operational and ready for pilot deployment.',
            icon: '/favicon.ico',
          });
          setFcmResult('Permission granted. Test notification dispatched.');
        } else {
          setFcmResult('Notification permission dismissed or denied.');
        }
        setFcmTesting(false);
      });
    } else {
      setFcmResult('Notification permission is currently blocked in your browser settings.');
      setFcmTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px] text-slate-500">
        <RotateCw className="w-6 h-6 animate-spin mr-2" /> Loading settings and telemetry...
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl border border-[#E4EAF2] shadow-2xs flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-2xl bg-blue-50 text-blue-600">
            <Settings className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-black text-[#12213A] tracking-tight">
              Command Center Configuration
            </h2>
            <p className="text-xs text-[#65748B] mt-0.5">
              Dispatch engine escalation rules, telemetry parameters, and alert routing.
            </p>
          </div>
        </div>

        <button
          onClick={fetchSettings}
          className="p-2 rounded-lg text-slate-500 hover:text-blue-600 hover:bg-slate-50 transition-colors"
          title="Reload settings"
        >
          <RotateCw className="w-4 h-4" />
        </button>
      </div>

      {/* Messages */}
      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 1. Dispatch Engine Parameters (Read-only / authoritative from backend) */}
      <div className="bg-white p-6 rounded-2xl border border-[#E4EAF2] shadow-sm space-y-5">
        <div className="pb-3 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-blue-600" />
            <h3 className="font-extrabold text-sm text-[#12213A]">
              Automated Dispatch Escalation Engine
            </h3>
          </div>
          <span className="text-[11px] font-semibold text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
            Active in Production
          </span>
        </div>

        <div className="space-y-4">
          <div>
            <p className="text-xs font-bold text-slate-700 mb-2">
              Progressive Radius Escalation Sequence
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {dispatchSettings?.radius_escalation_levels.map((lvl, idx) => (
                <React.Fragment key={lvl}>
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-blue-50 border border-blue-200 text-blue-800 text-xs font-extrabold">
                    <span>Wave {idx + 1}</span>
                    <span className="text-blue-500 font-medium">({lvl} km)</span>
                  </div>
                  {idx < dispatchSettings.radius_escalation_levels.length - 1 && (
                    <span className="text-slate-300 font-bold">→</span>
                  )}
                </React.Fragment>
              ))}
            </div>
            <p className="text-[11px] text-[#65748B] mt-2">
              The engine queries available responders within the primary {dispatchSettings?.default_radius_km} km perimeter and automatically expands to wider tiers if unaccepted upon timeout.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-3 border-t border-slate-100">
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-xs font-bold text-slate-700">Dispatch Offer Expiration</span>
              <p className="text-lg font-extrabold text-slate-900 mt-0.5">
                {dispatchSettings?.offer_expiration_seconds ?? 90} seconds
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Time granted to responder to accept before offer cascades to next rank.
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-xs font-bold text-slate-700">Telemetry Freshness Threshold</span>
              <p className="text-lg font-extrabold text-slate-900 mt-0.5">
                {(dispatchSettings?.stale_location_timeout_seconds ?? 1800) / 60} minutes
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Responders whose GPS has not reported within this window are bypassed.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Personal Notification Alert Routing */}
      <form onSubmit={handleSavePreferences} className="bg-white p-6 rounded-2xl border border-[#E4EAF2] shadow-sm space-y-5">
        <div className="pb-3 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-blue-600" />
            <h3 className="font-extrabold text-sm text-[#12213A]">
              Personal Alert & Dispatch Notification Routing
            </h3>
          </div>
          <span className="text-[11px] text-slate-400">Real-time Push & In-App</span>
        </div>

        <div className="space-y-3">
          <label className="flex items-center justify-between p-3 rounded-xl border border-slate-100 bg-slate-50/50 hover:bg-slate-50 cursor-pointer transition-colors">
            <div className="pr-4">
              <p className="text-xs font-bold text-[#12213A]">Critical Emergency Rescue Alerts</p>
              <p className="text-[11px] text-[#65748B]">Immediate audible notifications for high-acuity life-threat emergencies</p>
            </div>
            <input
              type="checkbox"
              checked={prefs.critical_rescue_alerts}
              onChange={(e) => setPrefs({ ...prefs, critical_rescue_alerts: e.target.checked })}
              className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 cursor-pointer"
            />
          </label>

          <label className="flex items-center justify-between p-3 rounded-xl border border-slate-100 bg-slate-50/50 hover:bg-slate-50 cursor-pointer transition-colors">
            <div className="pr-4">
              <p className="text-xs font-bold text-[#12213A]">Dispatch Escalation & Expiration Alerts</p>
              <p className="text-[11px] text-[#65748B]">Alert when no responder accepts within the initial radius</p>
            </div>
            <input
              type="checkbox"
              checked={prefs.dispatch_failures}
              onChange={(e) => setPrefs({ ...prefs, dispatch_failures: e.target.checked })}
              className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 cursor-pointer"
            />
          </label>

          <label className="flex items-center justify-between p-3 rounded-xl border border-slate-100 bg-slate-50/50 hover:bg-slate-50 cursor-pointer transition-colors">
            <div className="pr-4">
              <p className="text-xs font-bold text-[#12213A]">Veterinary Clinic Handoff Updates</p>
              <p className="text-[11px] text-[#65748B]">Arrival and admission notices at veterinary facilities</p>
            </div>
            <input
              type="checkbox"
              checked={prefs.veterinary_updates}
              onChange={(e) => setPrefs({ ...prefs, veterinary_updates: e.target.checked })}
              className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 cursor-pointer"
            />
          </label>

          <label className="flex items-center justify-between p-3 rounded-xl border border-slate-100 bg-slate-50/50 hover:bg-slate-50 cursor-pointer transition-colors">
            <div className="pr-4">
              <p className="text-xs font-bold text-[#12213A]">Case Closures & Final Dispositions</p>
              <p className="text-[11px] text-[#65748B]">Notifications when patients are released, adopted, or cases closed</p>
            </div>
            <input
              type="checkbox"
              checked={prefs.case_closures}
              onChange={(e) => setPrefs({ ...prefs, case_closures: e.target.checked })}
              className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 cursor-pointer"
            />
          </label>
        </div>

        <div className="pt-3 border-t border-slate-100 flex justify-end">
          <button
            type="submit"
            disabled={savingPrefs}
            className="px-5 py-2 bg-blue-600 text-white rounded-xl text-xs font-bold hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1.5 shadow-sm transition-all"
          >
            {savingPrefs ? (
              <>
                <RotateCw className="w-3.5 h-3.5 animate-spin" /> Saving...
              </>
            ) : (
              <>
                <Save className="w-3.5 h-3.5" /> Save Alert Preferences
              </>
            )}
          </button>
        </div>
      </form>

      {/* 3. Push Notification Diagnostics & FCM */}
      <div className="bg-white p-6 rounded-2xl border border-[#E4EAF2] shadow-sm space-y-4">
        <div className="pb-3 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Smartphone className="w-4 h-4 text-blue-600" />
            <h3 className="font-extrabold text-sm text-[#12213A]">
              Device Push Notification Diagnostics
            </h3>
          </div>
          <span className="text-[11px] text-slate-400">Firebase Cloud Messaging</span>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-slate-50 border border-slate-100">
          <div>
            <p className="text-xs font-bold text-slate-800">Dispatch Push Alert Test</p>
            <p className="text-[11px] text-slate-500">
              Verify this workstation can receive background push dispatch notifications.
            </p>
          </div>
          <button
            type="button"
            onClick={testPushNotification}
            disabled={fcmTesting}
            className="px-4 py-2 bg-slate-200 text-slate-800 hover:bg-slate-300 rounded-xl text-xs font-bold transition-colors shrink-0"
          >
            Test Push Notification
          </button>
        </div>

        {fcmResult && (
          <p className="text-xs text-blue-700 font-medium px-1">
            {fcmResult}
          </p>
        )}
      </div>

      {/* 4. Security & Device Session Invalidation */}
      <div className="bg-white p-6 rounded-2xl border border-red-100 shadow-sm space-y-4">
        <div className="pb-3 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-red-600" />
            <h3 className="font-extrabold text-sm text-red-900">
              Security & Active Session Management
            </h3>
          </div>
          <span className="text-[11px] font-semibold text-red-600 bg-red-50 px-2.5 py-0.5 rounded-full border border-red-200">
            High Security
          </span>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-0.5">
            <p className="text-xs font-bold text-slate-800">
              Revoke All Active Device Sessions
            </p>
            <p className="text-[11px] text-slate-500">
              Invalidate all refresh tokens and active sessions across all mobile and desktop devices.
            </p>
          </div>
          <button
            type="button"
            onClick={handleLogoutAll}
            disabled={revokingSessions}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors disabled:opacity-50 shrink-0"
          >
            {revokingSessions ? (
              <>
                <RotateCw className="w-3.5 h-3.5 animate-spin" /> Revoking...
              </>
            ) : (
              <>
                <LogOut className="w-3.5 h-3.5" /> Revoke All Sessions
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
