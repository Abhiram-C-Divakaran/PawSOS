import React, { useEffect, useState } from 'react';
import { 
  Users, 
  Search, 
  Filter, 
  CheckCircle2, 
  Clock, 
  Car, 
  AlertTriangle,
  RefreshCw,
  Power,
  Activity
} from 'lucide-react';
import api from '../../services/api';
import { formatApiError } from '../../utils/error';
import type { NGOResponderSummary } from '../../types';

export const NGOResponders: React.FC = () => {
  const [responders, setResponders] = useState<NGOResponderSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [availabilityFilter, setAvailabilityFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchResponders = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/ngo/responders');
      setResponders(res.data || []);
    } catch (err: any) {
      console.error('Error fetching responders', err);
      setError(formatApiError(err, 'Failed to load field responders'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const res = await api.get('/ngo/responders');
        if (active) setResponders(res.data || []);
      } catch (err: any) {
        if (active) setError(formatApiError(err, 'Failed to load field responders'));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, []);

  const handleToggleActive = async (responder: NGOResponderSummary) => {
    setUpdatingId(responder.user_id);
    setActionSuccess(null);
    setError(null);
    const newStatus = !responder.is_active;

    try {
      await api.patch(`/ngo/responders/${responder.user_id}/status`, {
        is_active: newStatus
      });
      setResponders((prev) =>
        prev.map((r) =>
          r.user_id === responder.user_id ? { ...r, is_active: newStatus } : r
        )
      );
      setActionSuccess(`Updated ${responder.full_name}'s status to ${newStatus ? 'Active' : 'Inactive'}`);
      setTimeout(() => setActionSuccess(null), 4000);
    } catch (err: any) {
      console.error('Failed to update responder status', err);
      setError(formatApiError(err, 'Failed to update responder status'));
    } finally {
      setUpdatingId(null);
    }
  };

  const filteredResponders = responders.filter((r) => {
    if (search) {
      const query = search.toLowerCase();
      const matchName = r.full_name?.toLowerCase().includes(query);
      const matchEmail = r.email?.toLowerCase().includes(query);
      const matchPhone = r.phone?.toLowerCase().includes(query);
      if (!matchName && !matchEmail && !matchPhone) return false;
    }
    if (availabilityFilter && r.availability_status !== availabilityFilter) {
      return false;
    }
    if (statusFilter) {
      const isActive = statusFilter === 'active';
      if (r.is_active !== isActive) return false;
    }
    return true;
  });

  const totalCount = responders.length;
  const availableCount = responders.filter((r) => r.is_active && r.availability_status === 'AVAILABLE').length;
  const onMissionCount = responders.filter((r) => !!r.active_case_number).length;
  const avgReliability = totalCount > 0 
    ? Math.round(responders.reduce((acc, r) => acc + (r.reliability_score || 0), 0) / totalCount)
    : 100;

  const getAvailabilityBadge = (status: string) => {
    switch (status) {
      case 'AVAILABLE':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            AVAILABLE
          </span>
        );
      case 'BUSY':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold rounded-md bg-amber-50 text-amber-800 border border-amber-200">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            ON MISSION
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md bg-slate-100 text-slate-600 border border-slate-200">
            <span className="w-2 h-2 rounded-full bg-slate-400" />
            OFFLINE
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-extrabold text-[#12213A] tracking-tight">
            Responder Fleet
          </h1>
          <p className="text-xs text-[#65748B] mt-0.5">
            Real-time readiness, active mission workload, and status management for field responders.
          </p>
        </div>
        <button
          onClick={fetchResponders}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl bg-white border border-[#E4EAF2] text-slate-700 hover:bg-slate-50 transition shadow-2xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Fleet
        </button>
      </div>

      {/* Alert Messages */}
      {actionSuccess && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
          <span>{actionSuccess}</span>
        </div>
      )}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Fleet KPI Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-2xl border border-[#E4EAF2] shadow-2xs">
          <div className="text-[11px] font-semibold text-[#65748B] uppercase tracking-wider">Total Responders</div>
          <div className="text-2xl font-black text-[#12213A] mt-1">{totalCount}</div>
          <div className="text-[11px] text-[#65748B] mt-1">Registered field fleet</div>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-[#E4EAF2] shadow-2xs">
          <div className="text-[11px] font-semibold text-[#65748B] uppercase tracking-wider">Available Now</div>
          <div className="text-2xl font-black text-emerald-600 mt-1">{availableCount}</div>
          <div className="text-[11px] text-[#65748B] mt-1">Ready for dispatch</div>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-[#E4EAF2] shadow-2xs">
          <div className="text-[11px] font-semibold text-[#65748B] uppercase tracking-wider">Active Missions</div>
          <div className="text-2xl font-black text-amber-600 mt-1">{onMissionCount}</div>
          <div className="text-[11px] text-[#65748B] mt-1">Currently on rescue cases</div>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-[#E4EAF2] shadow-2xs">
          <div className="text-[11px] font-semibold text-[#65748B] uppercase tracking-wider">Avg Reliability</div>
          <div className="text-2xl font-black text-blue-600 mt-1">{avgReliability}%</div>
          <div className="text-[11px] text-[#65748B] mt-1">Fleet composite score</div>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="bg-white p-4 rounded-2xl border border-[#E4EAF2] shadow-2xs flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by responder name, email, or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          <div className="flex items-center gap-1 text-xs text-[#65748B] font-medium">
            <Filter className="w-3.5 h-3.5" /> Filter:
          </div>
          <select
            value={availabilityFilter}
            onChange={(e) => setAvailabilityFilter(e.target.value)}
            className="px-3 py-2 text-xs font-medium bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Availability</option>
            <option value="AVAILABLE">Available</option>
            <option value="BUSY">On Mission (Busy)</option>
            <option value="OFFLINE">Offline</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-xs font-medium bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="active">Active Only</option>
            <option value="inactive">Inactive Only</option>
          </select>
        </div>
      </div>

      {/* Responders Table */}
      <div className="bg-white rounded-2xl border border-[#E4EAF2] shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-400">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-blue-600 mb-2" />
            <p className="text-xs font-medium">Loading responder fleet...</p>
          </div>
        ) : filteredResponders.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <Users className="w-8 h-8 mx-auto text-slate-300 mb-2" />
            <p className="text-sm font-bold text-[#12213A]">No responders found</p>
            <p className="text-xs text-[#65748B] mt-1">Try adjusting search filters or registering field personnel.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-[#E4EAF2] text-[11px] font-bold text-[#65748B] uppercase tracking-wider">
                  <th className="py-3.5 px-4">Responder</th>
                  <th className="py-3.5 px-4">Readiness</th>
                  <th className="py-3.5 px-4">Vehicle & Exp</th>
                  <th className="py-3.5 px-4">Active Mission</th>
                  <th className="py-3.5 px-4">Performance</th>
                  <th className="py-3.5 px-4">Reliability</th>
                  <th className="py-3.5 px-4">Last GPS Update</th>
                  <th className="py-3.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {filteredResponders.map((r) => {
                  const isUpdating = updatingId === r.user_id;
                  return (
                    <tr key={r.id} className="hover:bg-blue-50/40 transition-colors">
                      {/* Name & Contact */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-800 font-bold flex items-center justify-center text-xs shrink-0">
                            {r.full_name?.charAt(0) || 'R'}
                          </div>
                          <div>
                            <div className="font-bold text-[#12213A] flex items-center gap-1.5">
                              {r.full_name}
                              {!r.is_active && (
                                <span className="px-1.5 py-0.2 text-[10px] font-bold bg-slate-200 text-slate-600 rounded">
                                  INACTIVE
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-[#65748B] flex items-center gap-2 mt-0.5">
                              <span>{r.email}</span>
                              {r.phone && <span>• {r.phone}</span>}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Availability status */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {getAvailabilityBadge(r.availability_status)}
                      </td>

                      {/* Vehicle & Exp */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          {r.vehicle_available ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold bg-blue-50 text-blue-700 rounded-md">
                              <Car className="w-3.5 h-3.5" /> Vehicle
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs text-slate-500 bg-slate-100 rounded-md">
                              Foot Patrol
                            </span>
                          )}
                          <span className="text-xs font-medium text-slate-600">
                            {r.experience_level}
                          </span>
                        </div>
                      </td>

                      {/* Active Mission */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {r.active_case_number ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-bold bg-amber-50 text-amber-800 rounded-md border border-amber-200">
                            <Activity className="w-3 h-3 text-amber-600" />
                            {r.active_case_number}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400 font-medium">None</span>
                        )}
                      </td>

                      {/* Completed rescues & acceptance */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="text-xs">
                          <span className="font-bold text-[#12213A]">{r.completed_rescues}</span>
                          <span className="text-[#65748B]"> rescued</span>
                        </div>
                        <div className="text-[11px] text-[#65748B] mt-0.5">
                          {r.acceptance_rate_pct}% accept ({r.accepted_offers}/{r.total_offers} offers)
                        </div>
                      </td>

                      {/* Reliability Score */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <div className="w-12 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                r.reliability_score >= 85
                                  ? 'bg-emerald-500'
                                  : r.reliability_score >= 60
                                  ? 'bg-amber-500'
                                  : 'bg-red-500'
                              }`}
                              style={{ width: `${Math.min(100, Math.max(0, r.reliability_score))}%` }}
                            />
                          </div>
                          <span className="text-xs font-bold text-slate-700">
                            {Math.round(r.reliability_score)}%
                          </span>
                        </div>
                      </td>

                      {/* Last Location update */}
                      <td className="py-3.5 px-4 whitespace-nowrap text-xs text-[#65748B]">
                        {r.last_location_update ? (
                          <span className="inline-flex items-center gap-1">
                            <Clock className="w-3.5 h-3.5 text-slate-400" />
                            {new Date(r.last_location_update).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        ) : (
                          <span className="text-slate-400">No GPS data</span>
                        )}
                      </td>

                      {/* Action */}
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        <button
                          onClick={() => handleToggleActive(r)}
                          disabled={isUpdating}
                          className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-xl transition ${
                            r.is_active
                              ? 'bg-slate-100 text-slate-700 hover:bg-red-50 hover:text-red-700 border border-slate-200'
                              : 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-xs'
                          }`}
                          title={r.is_active ? 'Deactivate responder' : 'Activate responder'}
                        >
                          <Power className={`w-3.5 h-3.5 ${isUpdating ? 'animate-spin' : ''}`} />
                          {r.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
