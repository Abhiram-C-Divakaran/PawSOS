import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Search, Filter, ArrowUpRight, Clock } from 'lucide-react';
import api from '../../services/api';
import type { RescueCase, RescuePriority, RescueStatus } from '../../types';

function formatMinutesAgo(createdAt: string): string {
  const diffMs = Math.max(0, Date.now() - new Date(createdAt).getTime());
  const minutes = Math.round(diffMs / 60000);
  return minutes < 60 ? `${minutes}m ago` : `${Math.floor(minutes / 60)}h ago`;
}

export const NGOCases: React.FC = () => {
  const [cases, setCases] = useState<RescueCase[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [page, setPage] = useState<number>(0);
  const limit = 25;

  const fetchCases = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { skip: page * limit, limit };
      if (search) params.search = search;
      if (priorityFilter) params.priority = priorityFilter;
      if (statusFilter) params.status = statusFilter;

      const res = await api.get('/ngo/cases', { params });
      setCases(res.data || []);
    } catch (err) {
      console.error('Error fetching NGO cases', err);
    } finally {
      setLoading(false);
    }
  }, [page, limit, search, priorityFilter, statusFilter]);

  useEffect(() => {
    let mounted = true;
    const init = async () => {
      if (mounted) await fetchCases();
    };
    void init();
    return () => {
      mounted = false;
    };
  }, [fetchCases]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    fetchCases();
  };

  const getPriorityBadge = (p: RescuePriority) => {
    switch (p) {
      case 'CRITICAL':
        return <span className="px-2.5 py-0.5 text-xs font-extrabold bg-red-100 text-red-700 rounded-md">CRITICAL</span>;
      case 'URGENT':
        return <span className="px-2.5 py-0.5 text-xs font-bold bg-amber-100 text-amber-800 rounded-md">URGENT</span>;
      case 'MODERATE':
        return <span className="px-2.5 py-0.5 text-xs font-bold bg-blue-100 text-blue-800 rounded-md">MODERATE</span>;
      default:
        return <span className="px-2.5 py-0.5 text-xs font-semibold bg-emerald-100 text-emerald-800 rounded-md">GENERAL</span>;
    }
  };

  const getStatusBadge = (s: RescueStatus) => {
    switch (s) {
      case 'CLOSED':
      case 'RELEASED':
      case 'ADOPTED':
        return <span className="px-2.5 py-0.5 text-xs font-semibold bg-emerald-100 text-emerald-800 rounded-md">{s.replace(/_/g, ' ')}</span>;
      case 'SEARCHING_RESPONDER':
        return <span className="px-2.5 py-0.5 text-xs font-semibold bg-blue-50 text-blue-700 rounded-md">Searching</span>;
      case 'RESPONDER_EN_ROUTE':
        return <span className="px-2.5 py-0.5 text-xs font-semibold bg-cyan-50 text-cyan-800 rounded-md">En Route</span>;
      case 'UNDER_TREATMENT':
      case 'AT_VETERINARY_FACILITY':
        return <span className="px-2.5 py-0.5 text-xs font-semibold bg-purple-50 text-purple-700 rounded-md">Under Treatment</span>;
      default:
        return <span className="px-2.5 py-0.5 text-xs font-semibold bg-slate-100 text-slate-700 rounded-md">{s.replace(/_/g, ' ')}</span>;
    }
  };

  const getAnimalEmoji = (species?: string) => {
    const s = (species || '').toLowerCase();
    if (s.includes('dog')) return '🐕';
    if (s.includes('cat')) return '🐈';
    if (s.includes('cow') || s.includes('cattle')) return '🐄';
    if (s.includes('bird')) return '🕊️';
    return '🐾';
  };

  return (
    <div className="space-y-6">
      {/* Page Header Description */}
      <div>
        <h2 className="text-xl font-extrabold text-[#12213A] tracking-tight">Rescue Cases</h2>
        <p className="text-xs text-[#65748B] mt-0.5">
          Monitor, filter, and coordinate all active and historical animal rescue missions.
        </p>
      </div>

      {/* Controls Bar */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-[#E4EAF2] flex flex-col md:flex-row gap-3 justify-between items-center">
        <form onSubmit={handleSearchSubmit} className="w-full md:w-80 relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by case #, species, location..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
        </form>

        <div className="flex items-center gap-2 w-full md:w-auto flex-wrap">
          <div className="flex items-center gap-1.5 text-xs text-[#65748B] font-semibold">
            <Filter className="w-3.5 h-3.5" /> Filter:
          </div>

          <select
            value={priorityFilter}
            onChange={(e) => {
              setPriorityFilter(e.target.value);
              setPage(0);
            }}
            className="px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-700"
          >
            <option value="">All Priorities</option>
            <option value="CRITICAL">Critical</option>
            <option value="URGENT">Urgent</option>
            <option value="MODERATE">Moderate</option>
            <option value="GENERAL">General</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(0);
            }}
            className="px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-slate-700"
          >
            <option value="">All Statuses</option>
            <option value="TRIAGED">Triaged</option>
            <option value="SEARCHING_RESPONDER">Searching Responder</option>
            <option value="RESPONDER_ASSIGNED">Responder Assigned</option>
            <option value="RESPONDER_EN_ROUTE">En Route</option>
            <option value="RESCUED">Rescued</option>
            <option value="UNDER_TREATMENT">Under Treatment</option>
            <option value="RECOVERING">Recovering</option>
            <option value="CLOSED">Closed</option>
          </select>
        </div>
      </div>

      {/* Case Records Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-[#E4EAF2] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 text-[11px] font-bold uppercase text-[#65748B] tracking-wider border-b border-[#E4EAF2]">
                <th className="py-3.5 px-4">Case #</th>
                <th className="py-3.5 px-4">Animal</th>
                <th className="py-3.5 px-4">Priority</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Location</th>
                <th className="py-3.5 px-4">Reported</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs text-[#12213A]">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    Loading cases...
                  </td>
                </tr>
              ) : cases.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    No rescue cases matching current filters.
                  </td>
                </tr>
              ) : (
                cases.map((c) => (
                    <tr key={c.id} className="hover:bg-blue-50/40 transition-colors">
                      <td className="py-3.5 px-4 font-mono font-bold text-slate-900">{c.case_number}</td>
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1.5 font-semibold">
                          <span>{getAnimalEmoji(c.species)}</span>
                          <span>{c.species}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">{getPriorityBadge(c.triage_priority)}</td>
                      <td className="py-3.5 px-4">{getStatusBadge(c.status)}</td>
                      <td className="py-3.5 px-4 max-w-xs truncate text-[#65748B]">{c.address_text || 'GPS Coordinate'}</td>
                      <td className="py-3.5 px-4 whitespace-nowrap text-[#65748B]">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3 text-slate-400" />
                          {formatMinutesAgo(c.created_at)}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <Link
                          to={`/ngo/cases/${c.id}`}
                          className="inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition-colors"
                        >
                          View Dossier <ArrowUpRight className="w-3.5 h-3.5" />
                        </Link>
                      </td>
                    </tr>
                  ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 border-t border-[#E4EAF2] flex items-center justify-between text-xs text-[#65748B]">
          <span>
            Showing Page {page + 1} ({cases.length} records)
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1.5 border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed font-medium"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={cases.length < limit}
              className="px-3 py-1.5 border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed font-medium"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
