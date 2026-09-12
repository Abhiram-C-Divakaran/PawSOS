import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, Filter, ArrowUpRight, Clock } from 'lucide-react';
import api from '../../services/api';
import type { RescueCase, RescuePriority, RescueStatus } from '../../types';

export const NGOCases: React.FC = () => {
  const [cases, setCases] = useState<RescueCase[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [page, setPage] = useState<number>(0);
  const limit = 25;

  const fetchCases = async () => {
    setLoading(true);
    try {
      const params: any = { skip: page * limit, limit };
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
  };

  useEffect(() => {
    fetchCases();
  }, [page, priorityFilter, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    fetchCases();
  };

  const getPriorityBadge = (p: RescuePriority) => {
    switch (p) {
      case 'CRITICAL':
        return <span className="px-2 py-0.5 text-xs font-black bg-red-100 text-red-800 rounded-full">CRITICAL</span>;
      case 'URGENT':
        return <span className="px-2 py-0.5 text-xs font-bold bg-orange-100 text-orange-800 rounded-full">URGENT</span>;
      case 'MODERATE':
        return <span className="px-2 py-0.5 text-xs font-bold bg-blue-100 text-blue-800 rounded-full">MODERATE</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-semibold bg-stone-100 text-stone-700 rounded-full">GENERAL</span>;
    }
  };

  const getStatusBadge = (s: RescueStatus) => {
    const isClosed = s === 'CLOSED' || s === 'RELEASED' || s === 'ADOPTED';
    const isUnderway = s.includes('RESPONDER') || s === 'RESCUED' || s.includes('TREATMENT');
    return (
      <span
        className={`px-2 py-0.5 text-xs font-semibold rounded-md ${
          isClosed
            ? 'bg-emerald-100 text-emerald-800'
            : isUnderway
            ? 'bg-amber-100 text-amber-900'
            : 'bg-stone-100 text-stone-700'
        }`}
      >
        {s.replace(/_/g, ' ')}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Controls Bar */}
      <div className="bg-white p-4 rounded-2xl shadow-sm border border-stone-200 flex flex-col md:flex-row gap-3 justify-between items-center">
        <form onSubmit={handleSearchSubmit} className="w-full md:w-80 relative">
          <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by case #, species, street..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs border border-stone-300 rounded-xl focus:ring-2 focus:ring-amber-500 focus:outline-none"
          />
        </form>

        <div className="flex items-center gap-2 w-full md:w-auto flex-wrap">
          <div className="flex items-center gap-1.5 text-xs text-stone-500">
            <Filter className="w-3.5 h-3.5" /> Filter:
          </div>

          <select
            value={priorityFilter}
            onChange={(e) => {
              setPriorityFilter(e.target.value);
              setPage(0);
            }}
            className="px-2.5 py-1.5 text-xs border border-stone-300 rounded-lg bg-white focus:outline-none"
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
            className="px-2.5 py-1.5 text-xs border border-stone-300 rounded-lg bg-white focus:outline-none"
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
      <div className="bg-white rounded-2xl shadow-sm border border-stone-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-stone-50 text-[11px] font-bold uppercase text-stone-500 tracking-wider border-b border-stone-200">
                <th className="py-3.5 px-4">Case #</th>
                <th className="py-3.5 px-4">Animal</th>
                <th className="py-3.5 px-4">Priority</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Location</th>
                <th className="py-3.5 px-4">Reported</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100 text-xs text-stone-700">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-stone-400">
                    Loading cases...
                  </td>
                </tr>
              ) : cases.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-stone-400">
                    No rescue cases matching current filters.
                  </td>
                </tr>
              ) : (
                cases.map((c) => {
                  const minutesAgo = Math.round((Date.now() - new Date(c.created_at).getTime()) / 60000);
                  return (
                    <tr key={c.id} className="hover:bg-amber-50/40 transition-colors">
                      <td className="py-3.5 px-4 font-mono font-bold text-stone-900">{c.case_number}</td>
                      <td className="py-3.5 px-4 font-semibold text-stone-900">{c.species}</td>
                      <td className="py-3.5 px-4">{getPriorityBadge(c.triage_priority)}</td>
                      <td className="py-3.5 px-4">{getStatusBadge(c.status)}</td>
                      <td className="py-3.5 px-4 max-w-xs truncate text-stone-600">{c.address_text || 'GPS Coordinate'}</td>
                      <td className="py-3.5 px-4 whitespace-nowrap text-stone-500">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3 text-stone-400" />
                          {minutesAgo < 60 ? `${minutesAgo}m ago` : `${Math.floor(minutesAgo / 60)}h ago`}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <Link
                          to={`/ngo/cases/${c.id}`}
                          className="inline-flex items-center gap-1 text-xs font-bold text-amber-600 hover:text-amber-700 bg-amber-50 hover:bg-amber-100 px-3 py-1.5 rounded-lg transition-colors"
                        >
                          View Dossier <ArrowUpRight className="w-3.5 h-3.5" />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-4 border-t border-stone-100 flex items-center justify-between text-xs text-stone-500">
          <span>
            Showing Page {page + 1} ({cases.length} records)
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1.5 border border-stone-300 rounded-lg hover:bg-stone-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={cases.length < limit}
              className="px-3 py-1.5 border border-stone-300 rounded-lg hover:bg-stone-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
