import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  FileText,
  Clock,
  CheckCircle,
  XCircle,
  Calendar,
  Heart,
  AlertCircle,
  Trash2,
} from 'lucide-react';
import api from '../services/api';
import type { AdoptionApplication } from '../types';

export const MyAdoptionApplications: React.FC = () => {
  const location = useLocation();
  const [applications, setApplications] = useState<AdoptionApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSuccessToast, setShowSuccessToast] = useState(
    Boolean((location.state as any)?.submittedSuccess)
  );

  const fetchApplications = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get('/adoptions/my-applications');
      setApplications(Array.isArray(res.data) ? res.data : []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load adoption applications');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApplications();
  }, []);

  const handleWithdraw = async (appId: string) => {
    if (!confirm('Are you sure you want to withdraw this adoption application?')) return;
    try {
      await api.post(`/adoptions/applications/${appId}/withdraw`);
      fetchApplications();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to withdraw application');
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle className="w-3.5 h-3.5 mr-1 text-emerald-600" />
            APPLICATION APPROVED
          </span>
        );
      case 'VISIT_SCHEDULED':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
            <Calendar className="w-3.5 h-3.5 mr-1 text-blue-600" />
            MEET-AND-GREET SCHEDULED
          </span>
        );
      case 'UNDER_REVIEW':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3.5 h-3.5 mr-1 text-amber-600" />
            UNDER NGO REVIEW
          </span>
        );
      case 'REJECTED':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-red-50 text-red-700 border border-red-200">
            <XCircle className="w-3.5 h-3.5 mr-1 text-red-600" />
            NOT SELECTED
          </span>
        );
      case 'WITHDRAWN':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-gray-100 text-gray-700 border border-gray-200">
            WITHDRAWN
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-teal-50 text-teal-700 border border-teal-200">
            SUBMITTED
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-teal"></div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Toast */}
      {showSuccessToast && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-2xl flex items-center justify-between shadow-sm">
          <div className="flex items-center space-x-3 text-sm">
            <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <span>Your adoption application has been submitted successfully! The NGO will review it shortly.</span>
          </div>
          <button onClick={() => setShowSuccessToast(false)} className="text-emerald-700 font-bold text-xs ml-4">
            ✕
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Adoption Applications</h1>
          <p className="text-sm text-gray-500 mt-0.5">Track the status of your pet adoption requests and scheduled visits.</p>
        </div>
        <Link
          to="/adopt"
          className="px-4 py-2 bg-brand-teal hover:bg-teal-600 text-white text-sm font-semibold rounded-xl shadow-sm transition flex items-center space-x-1.5 self-start sm:self-auto"
        >
          <Heart className="w-4 h-4 fill-current" />
          <span>Browse More Pets</span>
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl flex items-center space-x-3 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-500" />
          <span>{error}</span>
        </div>
      )}

      {/* Applications List */}
      {applications.length === 0 ? (
        <div className="bg-white rounded-3xl p-16 text-center border border-gray-100 shadow-sm space-y-4">
          <FileText className="w-12 h-12 text-gray-300 mx-auto" />
          <h3 className="text-lg font-bold text-gray-800">No Applications Submitted</h3>
          <p className="text-sm text-gray-500 max-w-sm mx-auto">
            You haven't applied for any animals yet. Visit our adoption catalog to meet animals looking for forever families!
          </p>
          <Link
            to="/adopt"
            className="inline-block px-6 py-2.5 bg-brand-teal text-white rounded-xl font-bold text-sm shadow-sm transition hover:bg-teal-600"
          >
            Explore Adoption Catalog
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {applications.map((app) => (
            <div key={app.id} className="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-100 pb-4">
                <div className="flex items-center space-x-3">
                  <div className="w-12 h-12 rounded-xl bg-teal-50 text-brand-teal flex items-center justify-center flex-shrink-0">
                    <Heart className="w-6 h-6 fill-teal-100 text-brand-teal" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-gray-900">
                      {app.listing_title || app.listing?.title || 'Adoption Application'}
                    </h3>
                    <p className="text-xs text-gray-400">
                      Submitted on {app.created_at ? new Date(app.created_at).toLocaleDateString() : 'Recently'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  {getStatusBadge(app.status)}
                  {app.status !== 'APPROVED' && app.status !== 'REJECTED' && app.status !== 'WITHDRAWN' && (
                    <button
                      onClick={() => handleWithdraw(app.id)}
                      className="text-gray-400 hover:text-red-600 p-1.5 rounded-lg hover:bg-red-50 transition"
                      title="Withdraw application"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>

              {/* Scheduled visits block */}
              {app.visits && app.visits.length > 0 && (
                <div className="bg-blue-50/70 border border-blue-100 p-4 rounded-xl space-y-2">
                  <span className="text-xs font-bold text-blue-900 uppercase tracking-wider block flex items-center">
                    <Calendar className="w-4 h-4 mr-1.5 text-blue-600" />
                    Scheduled Meet & Greet
                  </span>
                  {app.visits.map((v) => (
                    <div key={v.id} className="text-xs text-blue-950 space-y-1">
                      <div>
                        <strong>Time: </strong> {new Date(v.scheduled_at).toLocaleString()}
                      </div>
                      <div>
                        <strong>Location: </strong> {v.location_address}
                      </div>
                      {v.notes && (
                        <div>
                          <strong>Instructions: </strong> {v.notes}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Notes or rejection reasons */}
              {app.reviewer_notes && (
                <div className="bg-gray-50 p-3.5 rounded-xl text-xs text-gray-600">
                  <span className="font-semibold text-gray-700 block mb-0.5">NGO Notes:</span>
                  {app.reviewer_notes}
                </div>
              )}

              {app.rejection_reason && (
                <div className="bg-red-50 p-3.5 rounded-xl text-xs text-red-700">
                  <span className="font-semibold text-red-800 block mb-0.5">Decision Note:</span>
                  {app.rejection_reason}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
