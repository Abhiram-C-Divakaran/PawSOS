import React, { useState, useEffect } from 'react';
import {
  CheckCircle,
  Send,
  Sparkles,
  AlertCircle,
} from 'lucide-react';
import api from '../../services/api';
import type { FosterHome, FosterCandidate, RescueCase, FosterAssignment } from '../../types';

export const NGOFoster: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'directory' | 'matching' | 'assignments'>('directory');
  const [homes, setHomes] = useState<FosterHome[]>([]);
  const [cases, setCases] = useState<RescueCase[]>([]);
  const [assignments, setAssignments] = useState<FosterAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Matching state
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');
  const [matchingCandidates, setMatchingCandidates] = useState<FosterCandidate[]>([]);
  const [matchingLoading, setMatchingLoading] = useState(false);

  // Offer modal state
  const [selectedHomeForOffer, setSelectedHomeForOffer] = useState<FosterCandidate | null>(null);
  const [offerNotes, setOfferNotes] = useState('');
  const [submittingOffer, setSubmittingOffer] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [homesRes, casesRes, assignRes] = await Promise.all([
        api.get('/ngo/foster/homes'),
        api.get('/ngo/cases?status=RECOVERING'),
        api.get('/ngo/foster/assignments'),
      ]);
      setHomes(homesRes.data || []);
      setCases(casesRes.data || []);
      setAssignments(assignRes.data || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load NGO foster operations data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleVerifyHome = async (homeId: string) => {
    try {
      await api.post(`/ngo/foster/homes/${homeId}/verify`);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to verify foster home');
    }
  };

  const handleFindMatches = async () => {
    if (!selectedCaseId) return;
    try {
      setMatchingLoading(true);
      const res = await api.post('/ngo/foster/matches', { case_id: selectedCaseId });
      setMatchingCandidates(res.data || []);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to compute foster matches');
    } finally {
      setMatchingLoading(false);
    }
  };

  const handleCreateOffer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedHomeForOffer || !selectedCaseId) return;
    try {
      setSubmittingOffer(true);
      await api.post('/ngo/foster/assignments', {
        rescue_case_id: selectedCaseId,
        foster_home_id: selectedHomeForOffer.foster_home_id,
        notes: offerNotes,
      });
      setSelectedHomeForOffer(null);
      setOfferNotes('');
      alert('Foster offer sent successfully to caregiver!');
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create foster offer');
    } finally {
      setSubmittingOffer(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-teal"></div>
      </div>
    );
  }

  const verifiedCount = homes.filter((h) => h.verified).length;
  const totalCapacity = homes.reduce((acc, h) => acc + (h.capacity || 0), 0);
  const totalOccupancy = homes.reduce((acc, h) => acc + (h.current_occupancy || 0), 0);

  return (
    <div className="space-y-6">
      {/* Top Title & Stats Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Foster Care Network</h1>
          <p className="text-sm text-gray-500">Coordinate temporary home placements, caregiver verification, and deterministic animal matching.</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl flex items-center space-x-3 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Affiliated Homes</span>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-gray-900">{homes.length}</span>
            <span className="text-xs text-emerald-600 font-medium">{verifiedCount} verified</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Capacity Occupancy</span>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-gray-900">{totalOccupancy}</span>
            <span className="text-xs text-gray-500">/ {totalCapacity} spaces</span>
          </div>
          <div className="w-full bg-gray-100 h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-brand-teal h-full"
              style={{ width: `${totalCapacity > 0 ? (totalOccupancy / totalCapacity) * 100 : 0}%` }}
            />
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Recovering Rescues</span>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-gray-900">{cases.length}</span>
            <span className="text-xs text-teal-600 font-medium">Eligible for foster</span>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Active Placements</span>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-gray-900">
              {assignments.filter((a) => a.status === 'ACTIVE').length}
            </span>
            <span className="text-xs text-blue-600 font-medium">In caregiver homes</span>
          </div>
        </div>
      </div>

      {/* Navigation tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          <button
            onClick={() => setActiveTab('directory')}
            className={`pb-3 text-sm font-semibold border-b-2 transition ${
              activeTab === 'directory'
                ? 'border-brand-teal text-brand-teal'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Foster Homes Directory ({homes.length})
          </button>
          <button
            onClick={() => setActiveTab('matching')}
            className={`pb-3 text-sm font-semibold border-b-2 transition flex items-center space-x-2 ${
              activeTab === 'matching'
                ? 'border-brand-teal text-brand-teal'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Sparkles className="w-4 h-4" />
            <span>Placement Matcher</span>
          </button>
          <button
            onClick={() => setActiveTab('assignments')}
            className={`pb-3 text-sm font-semibold border-b-2 transition ${
              activeTab === 'assignments'
                ? 'border-brand-teal text-brand-teal'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Placements & Care Updates ({assignments.length})
          </button>
        </nav>
      </div>

      {/* Tab 1: Homes Directory */}
      {activeTab === 'directory' && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-bold text-gray-900 text-sm">Affiliated Foster Homes</h3>
            <span className="text-xs text-gray-400">Strict privacy: exact coordinates masked</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-gray-100">
                <tr>
                  <th className="px-6 py-3">Caregiver</th>
                  <th className="px-6 py-3">Locality</th>
                  <th className="px-6 py-3">Capacity</th>
                  <th className="px-6 py-3">Accepted Species</th>
                  <th className="px-6 py-3">Medical Care</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {homes.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-gray-400">
                      No foster homes registered under your organization yet.
                    </td>
                  </tr>
                ) : (
                  homes.map((h) => (
                    <tr key={h.id} className="hover:bg-gray-50/50 transition">
                      <td className="px-6 py-4">
                        <div className="font-semibold text-gray-900">{h.caregiver?.full_name || 'Caregiver'}</div>
                        <div className="text-xs text-gray-400">{h.caregiver?.phone}</div>
                      </td>
                      <td className="px-6 py-4">{h.locality || 'Area unlisted'}</td>
                      <td className="px-6 py-4">
                        <span className="font-medium text-gray-900">
                          {h.current_occupancy} / {h.capacity}
                        </span>
                      </td>
                      <td className="px-6 py-4">{h.accepted_species || 'Dog, Cat'}</td>
                      <td className="px-6 py-4">
                        {h.medical_care_supported ? (
                          <span className="text-emerald-600 font-semibold text-xs">Supported</span>
                        ) : (
                          <span className="text-gray-400 text-xs">Basic</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                            h.verified
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}
                        >
                          {h.verified ? 'VERIFIED' : 'PENDING VERIFICATION'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        {!h.verified && (
                          <button
                            onClick={() => handleVerifyHome(h.id)}
                            className="px-3 py-1.5 bg-brand-teal hover:bg-teal-600 text-white text-xs font-semibold rounded-lg shadow-sm transition"
                          >
                            Verify Home
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: Placement Matcher */}
      {activeTab === 'matching' && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm space-y-4">
            <h3 className="text-base font-bold text-gray-900">Select a Recovering Rescue Animal</h3>
            <div className="flex flex-col sm:flex-row gap-4 items-center">
              <select
                value={selectedCaseId}
                onChange={(e) => setSelectedCaseId(e.target.value)}
                className="w-full sm:w-96 px-3.5 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-brand-teal focus:bg-white outline-none"
              >
                <option value="">-- Choose Recovering Animal --</option>
                {cases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.case_number} ({c.species}) - {c.description?.slice(0, 40) || 'Post-treatment'}
                  </option>
                ))}
              </select>

              <button
                onClick={handleFindMatches}
                disabled={!selectedCaseId || matchingLoading}
                className="w-full sm:w-auto px-6 py-2.5 bg-brand-teal hover:bg-teal-600 text-white text-sm font-bold rounded-xl shadow-sm transition disabled:opacity-50 flex items-center justify-center space-x-2"
              >
                <Sparkles className="w-4 h-4" />
                <span>{matchingLoading ? 'Computing Scores...' : 'Find Foster Matches'}</span>
              </button>
            </div>
          </div>

          {/* Matches result */}
          {matchingCandidates.length > 0 && (
            <div className="space-y-4">
              <h4 className="text-sm font-bold text-gray-700 uppercase tracking-wider">
                Ranked Compatible Foster Homes ({matchingCandidates.length})
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {matchingCandidates.map((cand) => (
                  <div
                    key={cand.foster_home_id}
                    className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition space-y-3"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h5 className="font-bold text-gray-900 text-base">{cand.caregiver_name}</h5>
                        <p className="text-xs text-gray-500">{cand.locality}</p>
                      </div>
                      <div className="text-right">
                        <span className="inline-block bg-teal-50 text-brand-teal font-extrabold text-sm px-2.5 py-1 rounded-lg border border-teal-100">
                          {cand.score} pts
                        </span>
                        {cand.distance_km !== null && cand.distance_km !== undefined && (
                          <span className="block text-[11px] text-gray-400 mt-0.5">~{cand.distance_km} km away</span>
                        )}
                      </div>
                    </div>

                    <div className="bg-gray-50 p-3 rounded-xl text-xs space-y-1">
                      <span className="font-semibold text-gray-500 uppercase tracking-wider block mb-1">
                        Matching Criteria
                      </span>
                      {cand.reasons.map((r, idx) => (
                        <div key={idx} className="text-gray-700 flex items-center space-x-1.5">
                          <CheckCircle className="w-3 h-3 text-brand-teal flex-shrink-0" />
                          <span>{r}</span>
                        </div>
                      ))}
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-gray-100 text-xs">
                      <span className="text-gray-500">
                        Remaining Capacity: <strong>{cand.remaining_capacity} spaces</strong>
                      </span>
                      <button
                        onClick={() => setSelectedHomeForOffer(cand)}
                        className="px-4 py-2 bg-brand-teal hover:bg-teal-600 text-white font-semibold rounded-lg shadow-sm transition flex items-center space-x-1"
                      >
                        <Send className="w-3.5 h-3.5" />
                        <span>Send Offer</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Assignments & Care Updates */}
      {activeTab === 'assignments' && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-gray-100">
            <h3 className="font-bold text-gray-900 text-sm">All Foster Placements</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-gray-100">
                <tr>
                  <th className="px-6 py-3">Case Number</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Start Date</th>
                  <th className="px-6 py-3">Notes</th>
                  <th className="px-6 py-3">Care Updates</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {assignments.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-gray-400">
                      No active or past foster placements found.
                    </td>
                  </tr>
                ) : (
                  assignments.map((a) => (
                    <tr key={a.id} className="hover:bg-gray-50/50 transition">
                      <td className="px-6 py-4 font-bold text-gray-900">
                        {a.rescue_case?.case_number || 'Animal Placement'}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                            a.status === 'ACTIVE'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : a.status === 'OFFERED'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {a.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-xs text-gray-500">
                        {a.start_date ? new Date(a.start_date).toLocaleDateString() : 'Pending Acceptance'}
                      </td>
                      <td className="px-6 py-4 text-xs text-gray-600 max-w-xs truncate">{a.notes || '—'}</td>
                      <td className="px-6 py-4 text-xs">
                        <span className="bg-gray-100 text-gray-700 px-2 py-0.5 rounded-full font-semibold">
                          {a.care_updates ? a.care_updates.length : 0} logs
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Offer Modal */}
      {selectedHomeForOffer && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <h3 className="text-lg font-bold text-gray-900">Send Foster Placement Offer</h3>
            <p className="text-xs text-gray-500">
              Offering placement to <strong>{selectedHomeForOffer.caregiver_name}</strong> ({selectedHomeForOffer.locality})
            </p>

            <form onSubmit={handleCreateOffer} className="space-y-4 text-sm">
              <div>
                <label className="block text-gray-700 font-semibold mb-1">Instructions / Care Notes</label>
                <textarea
                  rows={3}
                  placeholder="Provide dietary guidelines, medication instructions, and expected duration..."
                  value={offerNotes}
                  onChange={(e) => setOfferNotes(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal outline-none"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setSelectedHomeForOffer(null)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingOffer}
                  className="px-5 py-2 bg-brand-teal hover:bg-teal-600 text-white rounded-lg font-bold text-xs shadow-sm transition disabled:opacity-50"
                >
                  {submittingOffer ? 'Sending Offer...' : 'Send Offer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
