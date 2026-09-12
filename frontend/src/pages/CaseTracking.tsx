import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import api from '../services/api';
import { formatApiError } from '../utils/error';
import type { RescueCase, RescueTimeline } from '../types';
import { MapPin, AlertTriangle, Clock, CheckCircle, UserCheck, ShieldAlert } from 'lucide-react';
import { MapView } from '../components/MapView';

export const CaseTracking = () => {
  const { id } = useParams<{ id: string }>();
  const [rescueCase, setRescueCase] = useState<RescueCase | null>(null);
  const [timeline, setTimeline] = useState<RescueTimeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchCaseData = useCallback(async () => {
    try {
      const [caseRes, timelineRes] = await Promise.all([
        api.get(`/rescues/${id}`),
        api.get(`/rescues/${id}/timeline`)
      ]);
      setRescueCase(caseRes.data);
      setTimeline(timelineRes.data);
    } catch (err: any) {
      setError(formatApiError(err, 'Failed to load rescue case.'));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchCaseData();
    // Auto refresh every 10 seconds for real-time tracking
    const interval = setInterval(fetchCaseData, 10000);
    return () => clearInterval(interval);
  }, [fetchCaseData]);

  if (loading && !rescueCase) {
    return (
      <div className="max-w-3xl mx-auto py-16 text-center">
        <div className="inline-block w-8 h-8 border-4 border-brand-teal border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-gray-600 font-medium">Fetching real-time case data...</p>
      </div>
    );
  }

  if (error || !rescueCase) {
    return (
      <div className="max-w-md mx-auto py-16 text-center bg-white p-8 rounded-xl border border-gray-200 shadow-sm">
        <ShieldAlert className="w-12 h-12 text-rose-500 mx-auto mb-3" />
        <h2 className="text-lg font-bold text-gray-800 mb-1">Access Restricted</h2>
        <p className="text-gray-600 text-sm mb-4">{error || 'Case not found'}</p>
        <a href="/my-cases" className="inline-block bg-brand-darkNavy text-white px-5 py-2.5 rounded-lg text-sm font-semibold">
          Return to My Cases
        </a>
      </div>
    );
  }

  const primaryPhoto = rescueCase.images && rescueCase.images.length > 0
    ? rescueCase.images[0].image_url
    : null;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header Card */}
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col md:flex-row md:items-start justify-between gap-6">
        <div className="flex-1">
          <div className="flex items-center space-x-3 mb-2 flex-wrap gap-y-2">
            <h1 className="text-2xl font-bold text-brand-darkNavy">Case {rescueCase.case_number}</h1>
            <span className={`px-3 py-1 rounded-full text-xs font-bold tracking-wide ${
              rescueCase.triage_priority === 'CRITICAL' ? 'bg-red-100 text-red-700' :
              rescueCase.triage_priority === 'URGENT' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'
            }`}>
              {rescueCase.triage_priority} PRIORITY
            </span>
          </div>

          <p className="text-gray-500 flex items-center mb-4 text-sm">
            <span className="font-semibold text-gray-700 mr-2">{rescueCase.species}</span> • 
            <Clock className="w-4 h-4 mx-2 text-gray-400" />
            Reported {new Date(rescueCase.created_at).toLocaleString()}
          </p>
          
          <div className="flex flex-wrap gap-4">
            <div className="bg-gray-50 p-3.5 rounded-lg border border-gray-200">
              <span className="block text-xs text-gray-500 uppercase tracking-wider font-semibold mb-0.5">Current Status</span>
              <span className="text-lg font-bold text-brand-teal">{rescueCase.status.replace(/_/g, ' ')}</span>
            </div>

            {rescueCase.assigned_responder ? (
              <div className="bg-teal-50/70 p-3.5 rounded-lg border border-teal-200">
                <span className="block text-xs text-teal-700 uppercase tracking-wider font-semibold mb-0.5 flex items-center">
                  <UserCheck className="w-3.5 h-3.5 mr-1 text-teal-600" />
                  Assigned Responder
                </span>
                <span className="text-base font-bold text-teal-900">{rescueCase.assigned_responder.full_name}</span>
              </div>
            ) : (
              <div className="bg-amber-50 p-3.5 rounded-lg border border-amber-200">
                <span className="block text-xs text-amber-700 uppercase tracking-wider font-semibold mb-0.5">Responder Status</span>
                <span className="text-sm font-semibold text-amber-900">Searching nearby responders...</span>
              </div>
            )}
          </div>
        </div>
        
        {/* Real photo display */}
        {primaryPhoto ? (
          <div className="w-full md:w-48 h-36 bg-gray-100 rounded-xl flex items-center justify-center border border-gray-200 overflow-hidden shadow-sm flex-shrink-0">
            <img
              src={primaryPhoto}
              alt={`${rescueCase.species} rescue`}
              className="object-cover w-full h-full hover:scale-105 transition-transform duration-300"
            />
          </div>
        ) : (
          <div className="w-full md:w-48 h-36 bg-gray-50 rounded-xl flex flex-col items-center justify-center border border-dashed border-gray-300 text-gray-400 flex-shrink-0">
            <span className="text-xs font-medium">No photo uploaded</span>
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Details & Map Card */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 space-y-6">
          <div>
            <h3 className="font-semibold text-brand-darkNavy mb-2 flex items-center text-base">
              <MapPin className="w-4 h-4 mr-2 text-brand-teal" /> Location Pin
            </h3>
            <p className="text-gray-700 bg-gray-50 p-3 rounded-lg border border-gray-200 text-sm mb-3">
              {rescueCase.address_text}
            </p>
            <MapView
              lat={rescueCase.latitude}
              lng={rescueCase.longitude}
              title={`Case ${rescueCase.case_number} - ${rescueCase.species}`}
              height="200px"
            />
          </div>
          
          <div>
            <h3 className="font-semibold text-brand-darkNavy mb-2 flex items-center text-base">
              <AlertTriangle className="w-4 h-4 mr-2 text-brand-coral" /> Triage Assessment
            </h3>
            <div className="bg-orange-50 border border-orange-100 p-3.5 rounded-lg">
              <p className="text-xs font-bold text-orange-900 uppercase mb-1">Reason for Priority:</p>
              <p className="text-sm text-orange-800">{rescueCase.triage_reason || 'Standard rescue protocol'}</p>
            </div>
          </div>

          {rescueCase.description && (
            <div>
              <h3 className="font-semibold text-brand-darkNavy mb-1.5 text-base">Citizen Observations</h3>
              <p className="text-gray-700 bg-gray-50 p-3 rounded-lg border border-gray-200 text-sm leading-relaxed">
                "{rescueCase.description}"
              </p>
            </div>
          )}
        </div>

        {/* Timeline Card */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <h3 className="font-semibold text-brand-darkNavy mb-6 text-lg">Rescue Mission Timeline</h3>
          
          <div className="relative pl-8 space-y-7">
            <div className="absolute top-2 bottom-2 left-[11px] w-0.5 bg-gray-200"></div>
            
            {timeline.map((event, idx) => (
              <div key={event.id} className="relative">
                <div className={`absolute -left-[37px] w-6 h-6 rounded-full border-4 border-white flex items-center justify-center
                  ${idx === timeline.length - 1 ? 'bg-brand-teal ring-2 ring-teal-200' : 'bg-gray-300'}
                `}>
                  {idx !== timeline.length - 1 && <CheckCircle className="w-3.5 h-3.5 text-white" />}
                </div>
                <div>
                  <h4 className={`font-semibold text-sm ${idx === timeline.length - 1 ? 'text-brand-teal' : 'text-gray-700'}`}>
                    {event.new_status.replace(/_/g, ' ')}
                  </h4>
                  <p className="text-xs text-gray-400 mt-0.5">{new Date(event.created_at).toLocaleString()}</p>
                  {event.notes && (
                    <p className="text-xs text-gray-600 mt-1.5 bg-gray-50 p-2 rounded border border-gray-100">
                      {event.notes}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
