import React, { useState, useEffect } from 'react';
import {
  Home,
  Heart,
  CheckCircle,
  Clock,
  AlertTriangle,
  Send,
  PlusCircle,
  Edit2,
  FileText,
  Activity,
  XCircle,
} from 'lucide-react';
import api from '../services/api';
import type { FosterHome, FosterAssignment, FosterHomeAvailability } from '../types';

export const FosterDashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fosterHome, setFosterHome] = useState<FosterHome | null>(null);
  const [assignments, setAssignments] = useState<FosterAssignment[]>([]);
  const [activeTab, setActiveTab] = useState<'offers' | 'active' | 'history'>('offers');

  // Profile setup / edit state
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [locality, setLocality] = useState('');
  const [capacity, setCapacity] = useState(1);
  const [acceptedSpecies, setAcceptedSpecies] = useState('Dog, Cat');
  const [medicalCare, setMedicalCare] = useState(false);
  const [availabilityStatus, setAvailabilityStatus] = useState<FosterHomeAvailability>('AVAILABLE');
  const [submittingProfile, setSubmittingProfile] = useState(false);

  // Care update modal state
  const [selectedAssignment, setSelectedAssignment] = useState<FosterAssignment | null>(null);
  const [showUpdateModal, setShowUpdateModal] = useState(false);
  const [updateNotes, setUpdateNotes] = useState('');
  const [appetite, setAppetite] = useState('Normal');
  const [mobility, setMobility] = useState('Normal');
  const [medicationAdministered, setMedicationAdministered] = useState(false);
  const [behavioralNotes, setBehavioralNotes] = useState('');
  const [submittingUpdate, setSubmittingUpdate] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      // Try fetching existing profile
      try {
        const homeRes = await api.get('/foster/profile');
        setFosterHome(homeRes.data);
        setLocality(homeRes.data.locality || '');
        setCapacity(homeRes.data.capacity || 1);
        setAcceptedSpecies(homeRes.data.accepted_species || 'Dog, Cat');
        setMedicalCare(homeRes.data.medical_care_supported || false);
        setAvailabilityStatus(homeRes.data.availability_status || 'AVAILABLE');
      } catch (err: any) {
        if (err.response?.status === 404) {
          setFosterHome(null);
        } else {
          throw err;
        }
      }

      // Fetch assignments
      const assignRes = await api.get('/foster/assignments');
      setAssignments(assignRes.data || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load foster dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmittingProfile(true);
      const payload = {
        locality,
        capacity: Number(capacity),
        accepted_species: acceptedSpecies,
        medical_care_supported: medicalCare,
        availability_status: availabilityStatus,
      };

      if (fosterHome) {
        const res = await api.put('/foster/profile', payload);
        setFosterHome(res.data);
      } else {
        const res = await api.post('/foster/profile', payload);
        setFosterHome(res.data);
      }
      setShowProfileModal(false);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to save foster profile');
    } finally {
      setSubmittingProfile(false);
    }
  };

  const handleAcceptOffer = async (assignmentId: string) => {
    try {
      await api.post(`/foster/assignments/${assignmentId}/accept`);
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to accept foster offer');
    }
  };

  const handleDeclineOffer = async (assignmentId: string) => {
    const reason = prompt('Please enter a reason for declining (optional):');
    try {
      await api.post(`/foster/assignments/${assignmentId}/decline`, { reason: reason || 'Caregiver unavailable' });
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to decline foster offer');
    }
  };

  const handleSubmitCareUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAssignment) return;
    try {
      setSubmittingUpdate(true);
      await api.post(`/foster/assignments/${selectedAssignment.id}/updates`, {
        notes: updateNotes,
        appetite_status: appetite,
        mobility_status: mobility,
        medication_administered: medicationAdministered,
        behavioral_notes: behavioralNotes,
      });
      setShowUpdateModal(false);
      setUpdateNotes('');
      setBehavioralNotes('');
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to submit care update');
    } finally {
      setSubmittingUpdate(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-teal"></div>
      </div>
    );
  }

  const offers = assignments.filter((a) => a.status === 'OFFERED');
  const activePlacements = assignments.filter((a) => a.status === 'ACTIVE');
  const historyPlacements = assignments.filter((a) => a.status !== 'OFFERED' && a.status !== 'ACTIVE');

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
        <div className="flex items-center space-x-3">
          <div className="p-3 bg-teal-50 text-brand-teal rounded-xl">
            <Home className="w-8 h-8" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Foster Caregiver Hub</h1>
            <p className="text-sm text-gray-500">Manage your temporary pet care home, respond to offers, and record animal wellbeing.</p>
          </div>
        </div>

        {fosterHome ? (
          <button
            onClick={() => setShowProfileModal(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition"
          >
            <Edit2 className="w-4 h-4" />
            <span>Edit Profile</span>
          </button>
        ) : (
          <button
            onClick={() => setShowProfileModal(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-brand-teal hover:bg-teal-600 text-white rounded-lg text-sm font-medium transition shadow-sm"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Create Foster Profile</span>
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl flex items-center space-x-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-500" />
          <span>{error}</span>
        </div>
      )}

      {/* Foster Home Status Summary */}
      {fosterHome ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Verification</span>
            <div className="mt-2 flex items-center space-x-2">
              {fosterHome.verified ? (
                <>
                  <CheckCircle className="w-5 h-5 text-emerald-500" />
                  <span className="text-base font-semibold text-emerald-700">Verified Partner</span>
                </>
              ) : (
                <>
                  <Clock className="w-5 h-5 text-amber-500" />
                  <span className="text-base font-semibold text-amber-700">Pending NGO Review</span>
                </>
              )}
            </div>
            <p className="text-xs text-gray-400 mt-1">
              {fosterHome.verified ? 'Eligible for direct animal placements' : 'NGO will review your space and capacity'}
            </p>
          </div>

          <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Capacity & Occupancy</span>
            <div className="mt-2 flex items-baseline space-x-2">
              <span className="text-2xl font-bold text-gray-900">{fosterHome.current_occupancy}</span>
              <span className="text-sm text-gray-500">/ {fosterHome.capacity} spaces</span>
            </div>
            <div className="w-full bg-gray-100 h-2 rounded-full mt-2 overflow-hidden">
              <div
                className={`h-full ${
                  fosterHome.current_occupancy >= fosterHome.capacity ? 'bg-amber-500' : 'bg-brand-teal'
                }`}
                style={{ width: `${Math.min(100, (fosterHome.current_occupancy / fosterHome.capacity) * 100)}%` }}
              />
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Availability</span>
            <div className="mt-2">
              <span
                className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
                  fosterHome.availability_status === 'AVAILABLE'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : fosterHome.availability_status === 'FULL'
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : 'bg-gray-100 text-gray-700 border border-gray-200'
                }`}
              >
                {fosterHome.availability_status}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-2">Area: {fosterHome.locality || 'Locality set'}</p>
          </div>

          <div className="bg-white p-5 rounded-xl border border-gray-100 shadow-sm">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Capabilities</span>
            <div className="mt-2 text-sm text-gray-700 space-y-1">
              <div className="flex items-center justify-between">
                <span>Species:</span>
                <span className="font-medium text-gray-900">{fosterHome.accepted_species || 'All'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Medical Care:</span>
                <span className={`font-medium ${fosterHome.medical_care_supported ? 'text-emerald-600' : 'text-gray-500'}`}>
                  {fosterHome.medical_care_supported ? 'Yes' : 'Basic'}
                </span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-gradient-to-r from-teal-50 to-blue-50 border border-teal-200 p-8 rounded-2xl text-center">
          <Home className="w-12 h-12 text-brand-teal mx-auto mb-3" />
          <h2 className="text-xl font-bold text-gray-900">Become a Verified Foster Caregiver</h2>
          <p className="text-gray-600 max-w-lg mx-auto mt-2 text-sm">
            Provide a calm, safe environment for recovering rescue animals. Set up your home profile to receive matched placement offers from partner NGOs.
          </p>
          <button
            onClick={() => setShowProfileModal(true)}
            className="mt-5 px-6 py-2.5 bg-brand-teal hover:bg-teal-600 text-white font-medium rounded-xl shadow-sm transition"
          >
            Setup Profile Now
          </button>
        </div>
      )}

      {/* Tabs navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-6">
          <button
            onClick={() => setActiveTab('offers')}
            className={`pb-3 text-sm font-medium border-b-2 flex items-center space-x-2 ${
              activeTab === 'offers'
                ? 'border-brand-teal text-brand-teal'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <span>Placement Offers</span>
            {offers.length > 0 && (
              <span className="bg-brand-teal text-white text-xs px-2 py-0.5 rounded-full font-bold">
                {offers.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('active')}
            className={`pb-3 text-sm font-medium border-b-2 flex items-center space-x-2 ${
              activeTab === 'active'
                ? 'border-brand-teal text-brand-teal'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <span>Current Animals</span>
            {activePlacements.length > 0 && (
              <span className="bg-emerald-600 text-white text-xs px-2 py-0.5 rounded-full font-bold">
                {activePlacements.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`pb-3 text-sm font-medium border-b-2 ${
              activeTab === 'history'
                ? 'border-brand-teal text-brand-teal'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <span>History</span>
          </button>
        </nav>
      </div>

      {/* Tab 1: Offers */}
      {activeTab === 'offers' && (
        <div className="space-y-4">
          {offers.length === 0 ? (
            <div className="bg-white p-12 text-center rounded-2xl border border-gray-100">
              <Clock className="w-10 h-10 text-gray-300 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-gray-700">No Pending Placement Offers</h3>
              <p className="text-sm text-gray-400 mt-1">When an NGO matches a recovering rescue to your home, offers will appear here.</p>
            </div>
          ) : (
            offers.map((assignment) => (
              <div key={assignment.id} className="bg-white p-6 rounded-2xl border border-teal-100 shadow-sm hover:shadow-md transition flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <span className="bg-teal-50 text-teal-700 text-xs px-2.5 py-1 rounded-full font-semibold border border-teal-200">
                      OFFER PENDING
                    </span>
                    <span className="text-sm font-bold text-gray-900">
                      {assignment.rescue_case?.case_number || 'Rescue Animal'}
                    </span>
                    <span className="text-xs text-gray-400">({assignment.rescue_case?.species || 'Animal'})</span>
                  </div>
                  <p className="text-sm text-gray-600 max-w-xl">
                    {assignment.notes || assignment.rescue_case?.description || 'Caregiver assistance requested for post-treatment recovery.'}
                  </p>
                  <p className="text-xs text-gray-400">
                    Offered on {assignment.created_at ? new Date(assignment.created_at).toLocaleDateString() : 'Recently'}
                  </p>
                </div>

                <div className="flex items-center space-x-3 flex-shrink-0">
                  <button
                    onClick={() => handleDeclineOffer(assignment.id)}
                    className="px-4 py-2 border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-xl text-sm font-medium transition"
                  >
                    Decline
                  </button>
                  <button
                    onClick={() => handleAcceptOffer(assignment.id)}
                    className="px-5 py-2 bg-brand-teal hover:bg-teal-600 text-white rounded-xl text-sm font-medium shadow-sm transition flex items-center space-x-2"
                  >
                    <CheckCircle className="w-4 h-4" />
                    <span>Accept Placement</span>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 2: Current Placements */}
      {activeTab === 'active' && (
        <div className="space-y-4">
          {activePlacements.length === 0 ? (
            <div className="bg-white p-12 text-center rounded-2xl border border-gray-100">
              <Heart className="w-10 h-10 text-gray-300 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-gray-700">No Active Foster Placements</h3>
              <p className="text-sm text-gray-400 mt-1">Animals currently residing in your care will be shown here.</p>
            </div>
          ) : (
            activePlacements.map((assignment) => (
              <div key={assignment.id} className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="bg-emerald-50 text-emerald-700 text-xs px-2.5 py-1 rounded-full font-semibold border border-emerald-200">
                        IN CARE
                      </span>
                      <h3 className="text-lg font-bold text-gray-900">
                        {assignment.rescue_case?.case_number || 'Rescue Animal'}
                      </h3>
                      <span className="text-xs text-gray-500">({assignment.rescue_case?.species || 'Animal'})</span>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      Started: {assignment.start_date ? new Date(assignment.start_date).toLocaleDateString() : 'Active'}
                    </p>
                  </div>

                  <button
                    onClick={() => {
                      setSelectedAssignment(assignment);
                      setShowUpdateModal(true);
                    }}
                    className="px-4 py-2 bg-brand-teal hover:bg-teal-600 text-white text-sm font-medium rounded-xl shadow-sm transition flex items-center space-x-2"
                  >
                    <Activity className="w-4 h-4" />
                    <span>Record Care Update</span>
                  </button>
                </div>

                <div className="bg-gray-50 p-4 rounded-xl text-sm text-gray-700">
                  <span className="font-semibold text-xs text-gray-500 uppercase tracking-wider block mb-1">Placement Instructions</span>
                  {assignment.notes || 'Please provide quiet rest, nutritious food, and monitor condition.'}
                </div>

                {/* Display care updates if available */}
                {assignment.care_updates && assignment.care_updates.length > 0 && (
                  <div className="border-t border-gray-100 pt-3">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider block mb-2">Recent Care Updates</span>
                    <div className="space-y-2">
                      {assignment.care_updates.slice(0, 3).map((upd) => (
                        <div key={upd.id} className="bg-white p-3 rounded-lg border border-gray-100 text-xs text-gray-600 flex justify-between items-center">
                          <div>
                            <span className="font-medium text-gray-800">{upd.notes}</span>
                            <div className="text-gray-400 mt-0.5 space-x-2">
                              <span>Appetite: {upd.appetite_status || 'Normal'}</span>
                              <span>•</span>
                              <span>Mobility: {upd.mobility_status || 'Normal'}</span>
                              {upd.medication_administered && (
                                <>
                                  <span>•</span>
                                  <span className="text-emerald-600 font-medium">Medication Given</span>
                                </>
                              )}
                            </div>
                          </div>
                          <span className="text-gray-400">{new Date(upd.created_at).toLocaleDateString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 3: History */}
      {activeTab === 'history' && (
        <div className="space-y-3">
          {historyPlacements.length === 0 ? (
            <div className="bg-white p-12 text-center rounded-2xl border border-gray-100">
              <FileText className="w-10 h-10 text-gray-300 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-gray-700">No Past History</h3>
              <p className="text-sm text-gray-400 mt-1">Completed and archived placements will be listed here.</p>
            </div>
          ) : (
            historyPlacements.map((assignment) => (
              <div key={assignment.id} className="bg-white p-4 rounded-xl border border-gray-100 shadow-sm flex items-center justify-between">
                <div>
                  <span className="font-semibold text-gray-900 text-sm">
                    {assignment.rescue_case?.case_number || 'Past Placement'}
                  </span>
                  <span className="text-xs text-gray-400 ml-2">({assignment.rescue_case?.species || 'Animal'})</span>
                  <div className="text-xs text-gray-500 mt-0.5">
                    Status: <span className="font-medium">{assignment.status}</span>
                  </div>
                </div>
                <span className="text-xs text-gray-400">
                  {assignment.actual_end_date ? new Date(assignment.actual_end_date).toLocaleDateString() : 'Archived'}
                </span>
              </div>
            ))
          )}
        </div>
      )}

      {/* Profile Setup / Edit Modal */}
      {showProfileModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-xl">
            <div className="flex justify-between items-center border-b border-gray-100 pb-3">
              <h3 className="text-lg font-bold text-gray-900">
                {fosterHome ? 'Edit Foster Home Profile' : 'Setup Foster Home Profile'}
              </h3>
              <button onClick={() => setShowProfileModal(false)} className="text-gray-400 hover:text-gray-600">
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveProfile} className="space-y-4 text-sm">
              <div>
                <label className="block text-gray-700 font-medium mb-1">Neighborhood / Locality</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Bandra West, Mumbai"
                  value={locality}
                  onChange={(e) => setLocality(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal focus:border-transparent outline-none"
                />
                <p className="text-xs text-gray-400 mt-1">Coarse area name only. Exact street address is never exposed publicly.</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Capacity (Max Pets)</label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    required
                    value={capacity}
                    onChange={(e) => setCapacity(parseInt(e.target.value, 10))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal focus:border-transparent outline-none"
                  />
                </div>

                <div>
                  <label className="block text-gray-700 font-medium mb-1">Availability Status</label>
                  <select
                    value={availabilityStatus}
                    onChange={(e) => setAvailabilityStatus(e.target.value as FosterHomeAvailability)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal focus:border-transparent outline-none"
                  >
                    <option value="AVAILABLE">AVAILABLE</option>
                    <option value="TEMPORARILY_UNAVAILABLE">TEMPORARILY_UNAVAILABLE</option>
                    <option value="INACTIVE">INACTIVE</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Accepted Species</label>
                <input
                  type="text"
                  value={acceptedSpecies}
                  onChange={(e) => setAcceptedSpecies(e.target.value)}
                  placeholder="e.g. Dog, Cat, Bird"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal focus:border-transparent outline-none"
                />
              </div>

              <div className="flex items-center space-x-2 pt-1">
                <input
                  type="checkbox"
                  id="medicalCare"
                  checked={medicalCare}
                  onChange={(e) => setMedicalCare(e.target.checked)}
                  className="w-4 h-4 text-brand-teal rounded border-gray-300 focus:ring-brand-teal"
                />
                <label htmlFor="medicalCare" className="text-gray-700 font-medium cursor-pointer">
                  Can support specialized medication / post-surgical care
                </label>
              </div>

              <div className="flex justify-end space-x-3 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowProfileModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingProfile}
                  className="px-5 py-2 bg-brand-teal hover:bg-teal-600 text-white rounded-lg font-medium shadow-sm transition disabled:opacity-50"
                >
                  {submittingProfile ? 'Saving...' : 'Save Profile'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Care Update Modal */}
      {showUpdateModal && selectedAssignment && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-xl">
            <div className="flex justify-between items-center border-b border-gray-100 pb-3">
              <div>
                <h3 className="text-lg font-bold text-gray-900">Record Care Update</h3>
                <p className="text-xs text-gray-500">Case {selectedAssignment.rescue_case?.case_number || 'Placement'}</p>
              </div>
              <button onClick={() => setShowUpdateModal(false)} className="text-gray-400 hover:text-gray-600">
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmitCareUpdate} className="space-y-4 text-sm">
              <div>
                <label className="block text-gray-700 font-medium mb-1">Care Observation Notes *</label>
                <textarea
                  required
                  rows={3}
                  placeholder="Describe appetite, recovery progress, rest, and comfort level..."
                  value={updateNotes}
                  onChange={(e) => setUpdateNotes(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal focus:border-transparent outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-gray-700 font-medium mb-1">Appetite</label>
                  <select
                    value={appetite}
                    onChange={(e) => setAppetite(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal focus:border-transparent outline-none"
                  >
                    <option value="Normal">Normal</option>
                    <option value="Reduced">Reduced</option>
                    <option value="Increased">Increased</option>
                    <option value="Refusing Food">Refusing Food</option>
                  </select>
                </div>

                <div>
                  <label className="block text-gray-700 font-medium mb-1">Mobility</label>
                  <select
                    value={mobility}
                    onChange={(e) => setMobility(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal focus:border-transparent outline-none"
                  >
                    <option value="Normal">Normal</option>
                    <option value="Limping">Limping</option>
                    <option value="Restricted">Restricted / Bedrest</option>
                    <option value="Non-ambulatory">Non-ambulatory</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="medAdmin"
                  checked={medicationAdministered}
                  onChange={(e) => setMedicationAdministered(e.target.checked)}
                  className="w-4 h-4 text-brand-teal rounded border-gray-300 focus:ring-brand-teal"
                />
                <label htmlFor="medAdmin" className="text-gray-700 font-medium cursor-pointer">
                  Prescribed medication was administered
                </label>
              </div>

              <div>
                <label className="block text-gray-700 font-medium mb-1">Behavioral Observations</label>
                <input
                  type="text"
                  placeholder="e.g. Calm, playful, friendly with family members"
                  value={behavioralNotes}
                  onChange={(e) => setBehavioralNotes(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal focus:border-transparent outline-none"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowUpdateModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingUpdate}
                  className="px-5 py-2 bg-brand-teal hover:bg-teal-600 text-white rounded-lg font-medium shadow-sm transition disabled:opacity-50 flex items-center space-x-2"
                >
                  <Send className="w-4 h-4" />
                  <span>{submittingUpdate ? 'Submitting...' : 'Submit Care Update'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
