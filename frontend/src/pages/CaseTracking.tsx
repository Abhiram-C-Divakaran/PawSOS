import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../services/api';
import { RescueCase, RescueTimeline } from '../types';
import { MapPin, AlertTriangle, Clock, CheckCircle, Navigation } from 'lucide-react';

export const CaseTracking = () => {
  const { id } = useParams<{ id: string }>();
  const [rescueCase, setRescueCase] = useState<RescueCase | null>(null);
  const [timeline, setTimeline] = useState<RescueTimeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchCaseData = async () => {
    try {
      const [caseRes, timelineRes] = await Promise.all([
        api.get(`/rescues/${id}`),
        api.get(`/rescues/${id}/timeline`)
      ]);
      setRescueCase(caseRes.data);
      setTimeline(timelineRes.data);
    } catch (err) {
      setError('Failed to load rescue case.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCaseData();
    // Auto refresh every 10 seconds for MVP
    const interval = setInterval(fetchCaseData, 10000);
    return () => clearInterval(interval);
  }, [id]);

  if (loading && !rescueCase) return <div className="text-center py-12">Loading case details...</div>;
  if (error || !rescueCase) return <div className="text-center py-12 text-red-600">{error}</div>;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header Card */}
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3 mb-2">
            <h1 className="text-2xl font-bold text-brand-darkNavy">Case {rescueCase.case_number}</h1>
            <span className={`px-3 py-1 rounded-full text-xs font-bold tracking-wide ${
              rescueCase.triage_priority === 'CRITICAL' ? 'bg-red-100 text-red-700' :
              rescueCase.triage_priority === 'URGENT' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'
            }`}>
              {rescueCase.triage_priority}
            </span>
          </div>
          <p className="text-gray-500 flex items-center mb-4">
            <span className="font-medium mr-2">{rescueCase.species}</span> • 
            <Clock className="w-4 h-4 mx-2" /> Reported {new Date(rescueCase.created_at).toLocaleString()}
          </p>
          
          <div className="bg-gray-50 p-4 rounded-lg inline-block border border-gray-200">
            <span className="block text-sm text-gray-500 mb-1">Current Status</span>
            <span className="text-xl font-bold text-brand-teal">{rescueCase.status.replace(/_/g, ' ')}</span>
          </div>
        </div>
        
        {/* Placeholder for Photo map */}
        <div className="w-full md:w-48 h-32 bg-gray-100 rounded-lg flex items-center justify-center border border-gray-200 overflow-hidden relative">
           {/* If we had an image URL, we'd render it here */}
           <img src="https://res.cloudinary.com/demo/image/upload/sample.jpg" alt="Animal" className="object-cover w-full h-full opacity-80" />
           <div className="absolute inset-0 bg-black bg-opacity-10 flex items-center justify-center">
              <span className="bg-white/80 px-2 py-1 rounded text-xs font-medium">Photo attached</span>
           </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Details Card */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 space-y-6">
          <div>
            <h3 className="font-semibold text-brand-darkNavy mb-2 flex items-center">
              <MapPin className="w-4 h-4 mr-2 text-brand-teal" /> Location
            </h3>
            <p className="text-gray-700 bg-gray-50 p-3 rounded-lg border border-gray-200">{rescueCase.address_text}</p>
          </div>
          
          <div>
            <h3 className="font-semibold text-brand-darkNavy mb-2 flex items-center">
              <AlertTriangle className="w-4 h-4 mr-2 text-brand-coral" /> Emergency Assessment
            </h3>
            <div className="bg-orange-50 border border-orange-100 p-4 rounded-lg">
              <p className="text-sm font-medium text-orange-900 mb-2">Triage Reason:</p>
              <p className="text-sm text-orange-800">{rescueCase.triage_reason || 'Manual assessment required'}</p>
            </div>
          </div>

          {rescueCase.description && (
            <div>
              <h3 className="font-semibold text-brand-darkNavy mb-2">Description</h3>
              <p className="text-gray-700 bg-gray-50 p-3 rounded-lg border border-gray-200 text-sm">{rescueCase.description}</p>
            </div>
          )}
        </div>

        {/* Timeline Card */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <h3 className="font-semibold text-brand-darkNavy mb-6 text-lg">Rescue Timeline</h3>
          
          <div className="relative pl-8 space-y-8">
            <div className="absolute top-2 bottom-2 left-[11px] w-0.5 bg-gray-200"></div>
            
            {timeline.map((event, idx) => (
              <div key={event.id} className="relative">
                <div className={`absolute -left-[37px] w-6 h-6 rounded-full border-4 border-white flex items-center justify-center
                  ${idx === timeline.length - 1 ? 'bg-brand-teal' : 'bg-gray-300'}
                `}>
                  {idx !== timeline.length - 1 && <CheckCircle className="w-4 h-4 text-white" />}
                </div>
                <div>
                  <h4 className={`font-semibold ${idx === timeline.length - 1 ? 'text-brand-teal' : 'text-gray-700'}`}>
                    {event.new_status.replace(/_/g, ' ')}
                  </h4>
                  <p className="text-xs text-gray-500 mt-1">{new Date(event.created_at).toLocaleString()}</p>
                  {event.notes && (
                    <p className="text-sm text-gray-600 mt-2 bg-gray-50 p-2 rounded">{event.notes}</p>
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
