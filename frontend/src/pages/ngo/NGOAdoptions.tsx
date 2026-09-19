import React, { useState, useEffect } from 'react';
import {
  PlusCircle,
  CheckCircle,
  Calendar,
  AlertTriangle,
  FileText,
} from 'lucide-react';
import api from '../../services/api';
import type {
  AdoptionListing,
  AdoptionApplication,
  RescueCase,
} from '../../types';

export const NGOAdoptions: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'listings' | 'applications'>('applications');
  const [listings, setListings] = useState<AdoptionListing[]>([]);
  const [applications, setApplications] = useState<AdoptionApplication[]>([]);
  const [eligibleCases, setEligibleCases] = useState<RescueCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Application filter
  const [appFilter, setAppFilter] = useState('ALL');

  // Create Listing Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [listingTitle, setListingTitle] = useState('');
  const [publicDescription, setPublicDescription] = useState('');
  const [publicImageUrl, setPublicImageUrl] = useState('');
  const [locality, setLocality] = useState('');
  const [creatingListing, setCreatingListing] = useState(false);

  // Visit Scheduling Modal
  const [selectedAppForVisit, setSelectedAppForVisit] = useState<AdoptionApplication | null>(null);
  const [visitDateTime, setVisitDateTime] = useState('');
  const [visitType, setVisitType] = useState('HOME_VISIT');
  const [visitLocation, setVisitLocation] = useState('');
  const [visitNotes, setVisitNotes] = useState('');
  const [schedulingVisit, setSchedulingVisit] = useState(false);

  // Approval Modal
  const [selectedAppForApproval, setSelectedAppForApproval] = useState<AdoptionApplication | null>(null);
  const [decisionNotes, setDecisionNotes] = useState('');
  const [approving, setApproving] = useState(false);

  // Rejection Modal
  const [selectedAppForRejection, setSelectedAppForRejection] = useState<AdoptionApplication | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [rejecting, setRejecting] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [listingsRes, appsRes, eligibleRes] = await Promise.all([
        api.get('/ngo/adoptions/listings'),
        api.get('/ngo/adoptions/applications'),
        api.get('/ngo/adoptions/eligible-cases'),
      ]);
      setListings(Array.isArray(listingsRes.data) ? listingsRes.data : []);
      setApplications(Array.isArray(appsRes.data) ? appsRes.data : []);
      setEligibleCases(Array.isArray(eligibleRes.data) ? eligibleRes.data : []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load adoption operations data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void fetchData();
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, []);

  const handleCreateListing = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCaseId) return;
    try {
      setCreatingListing(true);
      await api.post('/ngo/adoptions/listings', {
        rescue_case_id: selectedCaseId,
        title: listingTitle,
        public_description: publicDescription,
        public_image_url: publicImageUrl || null,
        locality: locality || null,
      });
      setShowCreateModal(false);
      setSelectedCaseId('');
      setListingTitle('');
      setPublicDescription('');
      setPublicImageUrl('');
      setLocality('');
      alert('Adoption listing published successfully to public catalog!');
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to publish adoption listing');
    } finally {
      setCreatingListing(false);
    }
  };

  const handleMarkReview = async (appId: string) => {
    try {
      await api.post(`/ngo/adoptions/applications/${appId}/review`, { notes: 'Application initially reviewed by coordinator' });
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to mark under review');
    }
  };

  const handleScheduleVisit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAppForVisit) return;
    try {
      setSchedulingVisit(true);
      await api.post(`/ngo/adoptions/applications/${selectedAppForVisit.id}/visits`, {
        scheduled_at: new Date(visitDateTime).toISOString(),
        visit_type: visitType,
        location_address: visitLocation,
        notes: visitNotes,
      });
      setSelectedAppForVisit(null);
      setVisitDateTime('');
      setVisitLocation('');
      setVisitNotes('');
      alert('Visit scheduled successfully! Applicant has been notified.');
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to schedule visit');
    } finally {
      setSchedulingVisit(false);
    }
  };

  const handleApproveAdoption = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAppForApproval) return;
    try {
      setApproving(true);
      await api.post(`/ngo/adoptions/applications/${selectedAppForApproval.id}/approve`, {
        decision_notes: decisionNotes,
      });
      setSelectedAppForApproval(null);
      setDecisionNotes('');
      alert('Adoption approved and finalized! Case marked as ADOPTED and listing closed.');
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to approve adoption');
    } finally {
      setApproving(false);
    }
  };

  const handleRejectApplication = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAppForRejection) return;
    try {
      setRejecting(true);
      await api.post(`/ngo/adoptions/applications/${selectedAppForRejection.id}/reject`, {
        rejection_reason: rejectionReason,
      });
      setSelectedAppForRejection(null);
      setRejectionReason('');
      alert('Application rejected. Applicant has been notified.');
      fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to reject application');
    } finally {
      setRejecting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-teal"></div>
      </div>
    );
  }

  const filteredApps = applications.filter((app) => {
    if (appFilter === 'ALL') return true;
    return app.status === appFilter;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Adoption Operations</h1>
          <p className="text-sm text-gray-500">
            Publish verified rescue profiles to the citizen catalog, review applications, and finalize forever home placements.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center space-x-2 px-5 py-2.5 bg-brand-teal hover:bg-teal-600 text-white rounded-xl text-sm font-bold shadow-sm transition"
        >
          <PlusCircle className="w-4 h-4" />
          <span>Publish New Listing</span>
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl flex items-center space-x-3 text-sm">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-500" />
          <span>{error}</span>
        </div>
      )}

      {/* Quick KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Active Listings</span>
          <div className="mt-2 text-2xl font-bold text-gray-900">
            {listings.filter((l) => l.status === 'PUBLISHED').length}
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Pending Applications</span>
          <div className="mt-2 text-2xl font-bold text-amber-600">
            {applications.filter((a) => a.status === 'SUBMITTED' || a.status === 'UNDER_REVIEW').length}
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Scheduled Visits</span>
          <div className="mt-2 text-2xl font-bold text-blue-600">
            {applications.filter((a) => a.status === 'VISIT_SCHEDULED').length}
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Adopted Animals</span>
          <div className="mt-2 text-2xl font-bold text-emerald-600">
            {applications.filter((a) => a.status === 'APPROVED').length}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          <button
            onClick={() => setActiveTab('applications')}
            className={`pb-3 text-sm font-semibold border-b-2 transition flex items-center space-x-2 ${
              activeTab === 'applications'
                ? 'border-brand-teal text-brand-teal'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <span>Applications Inbox</span>
            {applications.length > 0 && (
              <span className="bg-brand-teal text-white text-xs px-2 py-0.5 rounded-full font-bold">
                {applications.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('listings')}
            className={`pb-3 text-sm font-semibold border-b-2 transition ${
              activeTab === 'listings'
                ? 'border-brand-teal text-brand-teal'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Adoption Listings ({listings.length})
          </button>
        </nav>
      </div>

      {/* Tab 1: Applications Inbox */}
      {activeTab === 'applications' && (
        <div className="space-y-4">
          {/* Status filter bar */}
          <div className="flex flex-wrap gap-2">
            {['ALL', 'SUBMITTED', 'UNDER_REVIEW', 'VISIT_SCHEDULED', 'APPROVED', 'REJECTED'].map((st) => (
              <button
                key={st}
                onClick={() => setAppFilter(st)}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
                  appFilter === st
                    ? 'bg-brand-teal text-white shadow-sm'
                    : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {filteredApps.length === 0 ? (
            <div className="bg-white p-12 text-center rounded-2xl border border-gray-100 shadow-sm">
              <FileText className="w-10 h-10 text-gray-300 mx-auto mb-2" />
              <h3 className="text-base font-bold text-gray-700">No applications in this view</h3>
              <p className="text-xs text-gray-400 mt-1">Submitted citizen applications will appear here.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredApps.map((app) => (
                <div key={app.id} className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-100 pb-3">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span
                          className={`text-xs px-2.5 py-0.5 rounded-full font-bold ${
                            app.status === 'APPROVED'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : app.status === 'VISIT_SCHEDULED'
                              ? 'bg-blue-50 text-blue-700 border border-blue-200'
                              : app.status === 'UNDER_REVIEW'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : app.status === 'REJECTED'
                              ? 'bg-red-50 text-red-700'
                              : 'bg-teal-50 text-teal-700 border border-teal-200'
                          }`}
                        >
                          {app.status}
                        </span>
                        <h3 className="font-bold text-gray-900 text-base">
                          {app.listing?.title || 'Adoption Candidate'}
                        </h3>
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">
                        Applicant: <strong>{app.applicant?.full_name}</strong> • {app.applicant?.phone} • {app.applicant?.email}
                      </p>
                    </div>

                    {/* Operational Action Buttons */}
                    <div className="flex flex-wrap items-center gap-2">
                      {app.status === 'SUBMITTED' && (
                        <button
                          onClick={() => handleMarkReview(app.id)}
                          className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold rounded-lg transition"
                        >
                          Mark Under Review
                        </button>
                      )}

                      {(app.status === 'SUBMITTED' || app.status === 'UNDER_REVIEW') && (
                        <button
                          onClick={() => setSelectedAppForVisit(app)}
                          className="px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-semibold rounded-lg transition flex items-center space-x-1"
                        >
                          <Calendar className="w-3.5 h-3.5" />
                          <span>Schedule Visit</span>
                        </button>
                      )}

                      {app.status !== 'APPROVED' && app.status !== 'REJECTED' && app.status !== 'WITHDRAWN' && (
                        <>
                          <button
                            onClick={() => setSelectedAppForRejection(app)}
                            className="px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-700 text-xs font-semibold rounded-lg transition"
                          >
                            Reject
                          </button>
                          <button
                            onClick={() => setSelectedAppForApproval(app)}
                            className="px-4 py-1.5 bg-brand-teal hover:bg-teal-600 text-white text-xs font-bold rounded-lg shadow-sm transition flex items-center space-x-1"
                          >
                            <CheckCircle className="w-3.5 h-3.5" />
                            <span>Approve & Finalize</span>
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Profile & Questionnaire Details */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-gray-50/70 p-3.5 rounded-xl">
                    <div>
                      <span className="text-gray-400 block">Housing</span>
                      <span className="font-semibold text-gray-800">{app.housing_type || 'Unspecified'}</span>
                    </div>
                    <div>
                      <span className="text-gray-400 block">Fenced Garden</span>
                      <span className="font-semibold text-gray-800">{app.has_fenced_garden ? 'Yes' : 'No'}</span>
                    </div>
                    <div>
                      <span className="text-gray-400 block">Other Pets</span>
                      <span className="font-semibold text-gray-800">{app.has_other_pets ? 'Yes' : 'None'}</span>
                    </div>
                    <div>
                      <span className="text-gray-400 block">Family Size</span>
                      <span className="font-semibold text-gray-800">{app.family_members_count || 1} people</span>
                    </div>
                  </div>

                  {/* Narrative details */}
                  <div className="space-y-2 text-xs">
                    {app.reason_for_adoption && (
                      <div>
                        <span className="font-bold text-gray-700 block">Reason for Adoption:</span>
                        <p className="text-gray-600 leading-relaxed bg-white p-2.5 rounded-lg border border-gray-100 mt-0.5">
                          {app.reason_for_adoption}
                        </p>
                      </div>
                    )}
                    {app.experience_with_pets && (
                      <div>
                        <span className="font-bold text-gray-700 block">Pet Experience:</span>
                        <p className="text-gray-600 bg-white p-2.5 rounded-lg border border-gray-100 mt-0.5">
                          {app.experience_with_pets}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Listings */}
      {activeTab === 'listings' && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 text-xs font-semibold text-gray-400 uppercase tracking-wider border-b border-gray-100">
                <tr>
                  <th className="px-6 py-3">Animal Title</th>
                  <th className="px-6 py-3">Species</th>
                  <th className="px-6 py-3">Locality</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Published Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {listings.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-gray-400">
                      No adoption listings created yet. Click "Publish New Listing" to add eligible animals.
                    </td>
                  </tr>
                ) : (
                  listings.map((l) => (
                    <tr key={l.id} className="hover:bg-gray-50/50 transition">
                      <td className="px-6 py-4 font-bold text-gray-900">{l.title}</td>
                      <td className="px-6 py-4">{l.species}</td>
                      <td className="px-6 py-4">{l.locality || 'General Area'}</td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                            l.status === 'PUBLISHED'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : l.status === 'ADOPTED'
                              ? 'bg-blue-50 text-blue-700 border border-blue-200'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {l.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-xs text-gray-400">
                        {l.published_at ? new Date(l.published_at).toLocaleDateString() : 'Draft'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Publish Listing Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-xl">
            <h3 className="text-lg font-bold text-gray-900">Publish Animal for Adoption</h3>
            <p className="text-xs text-gray-500">
              Only animals currently in <strong>READY_FOR_ADOPTION</strong> status are eligible for public listing.
            </p>

            <form onSubmit={handleCreateListing} className="space-y-4 text-sm">
              <div>
                <label className="block text-gray-700 font-semibold mb-1">Select Ready Animal *</label>
                <select
                  required
                  value={selectedCaseId}
                  onChange={(e) => {
                    setSelectedCaseId(e.target.value);
                    const chosen = eligibleCases.find((c) => c.id === e.target.value);
                    if (chosen && !listingTitle) {
                      setListingTitle(`Friendly ${chosen.species} looking for a loving home`);
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal outline-none"
                >
                  <option value="">-- Choose Eligible Case --</option>
                  {eligibleCases.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.case_number} ({c.species}) - {c.description?.slice(0, 40) || 'Ready'}
                    </option>
                  ))}
                </select>
                {eligibleCases.length === 0 && (
                  <p className="text-xs text-amber-600 mt-1">
                    No animals are currently in READY_FOR_ADOPTION status. Move post-treatment or foster cases to READY_FOR_ADOPTION first.
                  </p>
                )}
              </div>

              <div>
                <label className="block text-gray-700 font-semibold mb-1">Public Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Bella - Playful 1yo Golden Retriever"
                  value={listingTitle}
                  onChange={(e) => setListingTitle(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal outline-none"
                />
              </div>

              <div>
                <label className="block text-gray-700 font-semibold mb-1">Public Story & Traits</label>
                <textarea
                  rows={3}
                  placeholder="Describe personality, good with kids, energy level..."
                  value={publicDescription}
                  onChange={(e) => setPublicDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal outline-none"
                />
              </div>

              <div>
                <label className="block text-gray-700 font-semibold mb-1">Public Photo URL</label>
                <input
                  type="url"
                  placeholder="https://... (clean sanitized public photo)"
                  value={publicImageUrl}
                  onChange={(e) => setPublicImageUrl(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal outline-none"
                />
              </div>

              <div>
                <label className="block text-gray-700 font-semibold mb-1">Coarse Locality</label>
                <input
                  type="text"
                  placeholder="e.g. Bandra West, Mumbai"
                  value={locality}
                  onChange={(e) => setLocality(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal outline-none"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingListing || !selectedCaseId}
                  className="px-5 py-2 bg-brand-teal hover:bg-teal-600 text-white rounded-lg font-bold text-xs shadow-sm transition disabled:opacity-50"
                >
                  {creatingListing ? 'Publishing...' : 'Publish Listing'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Schedule Visit Modal */}
      {selectedAppForVisit && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <h3 className="text-lg font-bold text-gray-900">Schedule Meet & Greet Visit</h3>
            <p className="text-xs text-gray-500">
              Candidate: <strong>{selectedAppForVisit.applicant?.full_name}</strong> for {selectedAppForVisit.listing?.title}
            </p>

            <form onSubmit={handleScheduleVisit} className="space-y-4 text-sm">
              <div>
                <label className="block text-gray-700 font-semibold mb-1">Date & Time *</label>
                <input
                  type="datetime-local"
                  required
                  value={visitDateTime}
                  onChange={(e) => setVisitDateTime(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal outline-none"
                />
              </div>

              <div>
                <label className="block text-gray-700 font-semibold mb-1">Visit Type</label>
                <select
                  value={visitType}
                  onChange={(e) => setVisitType(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal outline-none"
                >
                  <option value="HOME_VISIT">Home Inspection & Meeting</option>
                  <option value="SHELTER_VISIT">Shelter / Facility Meeting</option>
                  <option value="FOSTER_HOME_VISIT">Foster Home Meeting</option>
                </select>
              </div>

              <div>
                <label className="block text-gray-700 font-semibold mb-1">Meeting Location *</label>
                <input
                  type="text"
                  required
                  placeholder="Address or shelter location"
                  value={visitLocation}
                  onChange={(e) => setVisitLocation(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal outline-none"
                />
              </div>

              <div>
                <label className="block text-gray-700 font-semibold mb-1">Instructions for Applicant</label>
                <textarea
                  rows={2}
                  placeholder="Please bring ID proof, ensure all household members are present..."
                  value={visitNotes}
                  onChange={(e) => setVisitNotes(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal outline-none"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setSelectedAppForVisit(null)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={schedulingVisit}
                  className="px-5 py-2 bg-brand-teal hover:bg-teal-600 text-white rounded-lg font-bold text-xs shadow-sm transition disabled:opacity-50"
                >
                  {schedulingVisit ? 'Scheduling...' : 'Confirm Visit'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Approve Modal */}
      {selectedAppForApproval && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl border-2 border-emerald-500">
            <div className="flex items-center space-x-3 text-emerald-700">
              <CheckCircle className="w-8 h-8" />
              <div>
                <h3 className="text-lg font-bold text-gray-900">Approve & Finalize Adoption</h3>
                <p className="text-xs text-gray-500">Final placement confirmation</p>
              </div>
            </div>

            <div className="bg-amber-50 border border-amber-200 p-3.5 rounded-xl text-xs text-amber-800 space-y-1">
              <span className="font-bold flex items-center">
                <AlertTriangle className="w-4 h-4 mr-1 flex-shrink-0" />
                Automatic Cascade Action:
              </span>
              <p>
                Approving <strong>{selectedAppForApproval.applicant?.full_name}</strong> will:
              </p>
              <ul className="list-disc list-inside space-y-0.5 text-[11px] pt-1 text-amber-900">
                <li>Transition animal status from READY_FOR_ADOPTION → <strong>ADOPTED</strong>.</li>
                <li>Close the public adoption listing permanently.</li>
                <li>Automatically reject and notify all other pending applicants.</li>
                <li>Complete and close any active foster assignment for this animal.</li>
              </ul>
            </div>

            <form onSubmit={handleApproveAdoption} className="space-y-4 text-sm">
              <div>
                <label className="block text-gray-700 font-semibold mb-1">Decision / Finalization Notes</label>
                <textarea
                  rows={2}
                  placeholder="e.g. Home inspection verified, adoption contract signed."
                  value={decisionNotes}
                  onChange={(e) => setDecisionNotes(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal outline-none"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setSelectedAppForApproval(null)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={approving}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold text-xs shadow-sm transition disabled:opacity-50"
                >
                  {approving ? 'Finalizing...' : 'Confirm Approval & Finalize'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {selectedAppForRejection && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <h3 className="text-lg font-bold text-gray-900">Reject Application</h3>
            <p className="text-xs text-gray-500">
              Applicant: <strong>{selectedAppForRejection.applicant?.full_name}</strong>
            </p>

            <form onSubmit={handleRejectApplication} className="space-y-4 text-sm">
              <div>
                <label className="block text-gray-700 font-semibold mb-1">Reason for Rejection *</label>
                <textarea
                  required
                  rows={3}
                  placeholder="e.g. Selected another applicant with larger outdoor space..."
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal outline-none"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setSelectedAppForRejection(null)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 font-medium text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={rejecting}
                  className="px-5 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-bold text-xs shadow-sm transition disabled:opacity-50"
                >
                  {rejecting ? 'Rejecting...' : 'Confirm Rejection'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
