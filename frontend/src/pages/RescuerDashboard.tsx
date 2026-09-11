import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { RescueCase, RescueStatus } from '../types';
import { MapPin, AlertTriangle, Clock, Map as MapIcon, ChevronRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const RescuerDashboard = () => {
  const [nearbyCases, setNearbyCases] = useState<RescueCase[]>([]);
  const [activeCase, setActiveCase] = useState<RescueCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { user } = useAuth();

  const fetchCases = async () => {
    try {
      // Find if rescuer already has an active case assigned to them that isn't closed
      // For MVP, we'll fetch nearby cases and filter if the user is the assigned responder (if backend exposed that)
      // Since backend doesn't currently return `assigned_rescuer_id` directly on the rescue model in `RescueResponse`, 
      // we might just rely on status transition attempts or fetch all and check.
      // We will assume the backend /nearby returns cases available to claim (TRIAGED, SEARCHING_RESPONDER).
      
      const response = await api.get('/rescues/nearby', {
        params: { lat: 19.0760, lng: 72.8777 } // Mocking location
      });
      setNearbyCases(response.data);
    } catch (err) {
      setError('Failed to fetch nearby cases.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
    const interval = setInterval(fetchCases, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleAccept = async (caseId: string) => {
    try {
      await api.post(`/rescues/${caseId}/accept`);
      // Re-fetch to get updated state, or simulate active case selection
      // Since we just accepted it, let's fetch its details to become active
      const caseRes = await api.get(`/rescues/${caseId}`);
      setActiveCase(caseRes.data);
      fetchCases();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to accept rescue. Someone else might have claimed it.');
      fetchCases();
    }
  };

  const handleStatusUpdate = async (newStatus: RescueStatus) => {
    if (!activeCase) return;
    try {
      const response = await api.patch(`/rescues/${activeCase.id}/status`, {
        status: newStatus,
        notes: `Status updated to ${newStatus}`
      });
      setActiveCase(response.data);
      if (['AT_VETERINARY_FACILITY', 'CLOSED'].includes(newStatus)) {
        setActiveCase(null); // Clear active case from rescuer view
        fetchCases();
      }
    } catch (err) {
      alert('Failed to update status.');
    }
  };

  const nextValidStatuses: Record<string, RescueStatus[]> = {
    'RESPONDER_ASSIGNED': ['RESPONDER_EN_ROUTE'],
    'RESPONDER_EN_ROUTE': ['ANIMAL_LOCATED'],
    'ANIMAL_LOCATED': ['RESCUED'],
    'RESCUED': ['TRANSPORTING'],
    'TRANSPORTING': ['AT_VETERINARY_FACILITY'],
  };

  if (loading && nearbyCases.length === 0) return <div className="text-center py-12">Locating cases...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex justify-between items-center bg-brand-darkNavy text-white p-4 rounded-xl shadow-md">
        <div>
          <h1 className="text-xl font-bold">Responder Dashboard</h1>
          <p className="text-gray-300 text-sm">Status: <span className="text-green-400 font-semibold">Available</span></p>
        </div>
      </div>

      {activeCase ? (
        <div className="bg-white rounded-xl shadow-lg border border-brand-teal overflow-hidden">
          <div className="bg-brand-softMint px-6 py-4 border-b border-brand-teal flex justify-between items-center">
            <h2 className="text-lg font-bold text-brand-darkNavy flex items-center">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse mr-2"></span>
              Active Rescue Mission
            </h2>
            <span className="font-mono text-sm bg-white px-2 py-1 rounded border border-gray-200">
              {activeCase.case_number}
            </span>
          </div>
          
          <div className="p-6">
            <div className="grid md:grid-cols-2 gap-6 mb-6">
              <div>
                <h3 className="text-gray-500 text-sm">Animal</h3>
                <p className="font-bold text-lg">{activeCase.species}</p>
                <div className="mt-4">
                  <h3 className="text-gray-500 text-sm">Condition</h3>
                  <p className="bg-orange-50 text-orange-800 p-3 rounded text-sm mt-1 border border-orange-100">
                    {activeCase.triage_reason}
                  </p>
                </div>
              </div>
              <div>
                <h3 className="text-gray-500 text-sm mb-1">Location</h3>
                <div className="flex items-start bg-gray-50 p-3 rounded border border-gray-200">
                  <MapPin className="w-5 h-5 text-brand-teal mr-2 flex-shrink-0 mt-0.5" />
                  <p className="text-sm font-medium">{activeCase.address_text}</p>
                </div>
                <button className="w-full mt-3 bg-brand-darkNavy text-white py-2 rounded font-medium flex items-center justify-center hover:bg-brand-deepNavy">
                  <MapIcon className="w-4 h-4 mr-2" /> Open in Maps
                </button>
              </div>
            </div>

            <div className="border-t border-gray-100 pt-6">
              <h3 className="text-sm font-bold text-gray-700 mb-3 uppercase tracking-wider">Update Status</h3>
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200 flex flex-col items-center">
                <span className="text-brand-teal font-bold text-lg mb-4 text-center">
                  Current: {activeCase.status.replace(/_/g, ' ')}
                </span>
                
                <div className="w-full max-w-sm space-y-3">
                  {(nextValidStatuses[activeCase.status] || []).map((nextStatus) => (
                    <button
                      key={nextStatus}
                      onClick={() => handleStatusUpdate(nextStatus)}
                      className="w-full bg-brand-coral hover:bg-red-500 text-white font-bold py-3 px-4 rounded-lg shadow transition-colors flex items-center justify-between"
                    >
                      <span>Mark as {nextStatus.replace(/_/g, ' ')}</span>
                      <ChevronRight className="w-5 h-5" />
                    </button>
                  ))}
                  
                  {(!nextValidStatuses[activeCase.status] || nextValidStatuses[activeCase.status].length === 0) && (
                    <p className="text-gray-500 text-sm text-center">No further actions available or awaiting vet handoff.</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div>
          <h2 className="text-xl font-bold text-brand-darkNavy mb-4">Nearby Emergencies</h2>
          {nearbyCases.length === 0 ? (
            <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-100 text-center">
              <p className="text-gray-500">No active rescue requests nearby.</p>
            </div>
          ) : (
            <div className="grid gap-4">
              {nearbyCases.map((rescue) => (
                <div key={rescue.id} className="bg-white p-5 rounded-xl shadow-sm border-l-4 border-l-red-500 border border-gray-100 hover:shadow-md transition-shadow">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <span className="bg-red-100 text-red-800 text-xs font-bold px-2 py-1 rounded mb-2 inline-block">
                        {rescue.triage_priority}
                      </span>
                      <h3 className="font-bold text-lg text-brand-darkNavy">{rescue.species} rescue</h3>
                    </div>
                    <span className="text-sm text-gray-500 flex items-center">
                      <Clock className="w-4 h-4 mr-1" />
                      {Math.round((Date.now() - new Date(rescue.created_at).getTime()) / 60000)} min ago
                    </span>
                  </div>
                  
                  <p className="text-gray-600 text-sm mb-4 line-clamp-1">{rescue.triage_reason}</p>
                  
                  <div className="flex justify-between items-center pt-3 border-t border-gray-100">
                    <div className="text-sm font-medium text-gray-600 flex items-center">
                      <MapPin className="w-4 h-4 mr-1 text-brand-teal" />
                      {rescue.address_text} (2.3 km)
                    </div>
                    <button
                      onClick={() => handleAccept(rescue.id)}
                      className="bg-brand-darkNavy hover:bg-brand-deepNavy text-white px-4 py-2 rounded font-medium shadow-sm transition-colors"
                    >
                      Accept Rescue
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
