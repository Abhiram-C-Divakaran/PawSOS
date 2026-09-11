import { useEffect, useState } from 'react';
import api from '../services/api';
import type { RescueCase, RescueStatus, VeterinaryFacility } from '../types';
import { MapPin, Clock, ChevronRight, Crosshair, Building2, CheckCircle } from 'lucide-react';
import { MapView } from '../components/MapView';
import { Toast, type ToastMessage } from '../components/Toast';

export const RescuerDashboard = () => {
  const [nearbyCases, setNearbyCases] = useState<RescueCase[]>([]);
  const [activeCase, setActiveCase] = useState<RescueCase | null>(null);
  const [facilities, setFacilities] = useState<VeterinaryFacility[]>([]);
  const [selectedFacilityId, setSelectedFacilityId] = useState<string>('');
  
  const [loading, setLoading] = useState(true);
  const [rescuerCoords, setRescuerCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [locating, setLocating] = useState(false);
  const [toast, setToast] = useState<ToastMessage | null>(null);

  const fetchFacilities = async () => {
    try {
      const res = await api.get('/veterinary/facilities');
      setFacilities(res.data);
      if (res.data.length > 0) {
        setSelectedFacilityId(res.data[0].id);
      }
    } catch (err) {
      console.error('Failed to load facilities', err);
    }
  };

  const syncLocationAndFetchNearby = async (lat: number, lng: number) => {
    try {
      // Sync rescuer operational GPS location to backend
      await api.patch('/rescuers/me/location', { latitude: lat, longitude: lng });

      // Fetch nearby open cases with real spatial distance
      const response = await api.get('/rescues/nearby', {
        params: { lat, lng, radius_km: 15.0 },
      });
      setNearbyCases(response.data);
    } catch (err: any) {
      setToast({
        id: 'nearby-err',
        type: 'error',
        message: err.response?.data?.detail || 'Failed to fetch nearby emergencies.',
      });
    } finally {
      setLoading(false);
      setLocating(false);
    }
  };

  const detectLocation = () => {
    if (!navigator.geolocation) {
      setToast({
        id: 'no-geo',
        type: 'warning',
        message: 'Geolocation is unavailable on this device.',
      });
      setLoading(false);
      return;
    }

    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords = {
          lat: Number(pos.coords.latitude.toFixed(6)),
          lng: Number(pos.coords.longitude.toFixed(6)),
        };
        setRescuerCoords(coords);
        syncLocationAndFetchNearby(coords.lat, coords.lng);
      },
      (_err) => {
        setLocating(false);
        setLoading(false);
        setToast({
          id: 'geo-denied',
          type: 'warning',
          message: 'Location access denied. Using last known station coordinates.',
        });
        // Fallback to station coordinates for demo testing if browser denies permission
        const defaultCoords = { lat: 19.0760, lng: 72.8777 };
        setRescuerCoords(defaultCoords);
        syncLocationAndFetchNearby(defaultCoords.lat, defaultCoords.lng);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  useEffect(() => {
    fetchFacilities();
    detectLocation();

    const interval = setInterval(() => {
      if (rescuerCoords) {
        syncLocationAndFetchNearby(rescuerCoords.lat, rescuerCoords.lng);
      }
    }, 15000);

    return () => clearInterval(interval);
  }, []);

  const handleAccept = async (caseId: string) => {
    try {
      await api.post(`/rescues/${caseId}/accept`);
      const caseRes = await api.get(`/rescues/${caseId}`);
      setActiveCase(caseRes.data);
      setToast({
        id: 'accepted',
        type: 'success',
        message: `Rescue mission ${caseRes.data.case_number} assigned to you.`,
      });
      if (rescuerCoords) {
        syncLocationAndFetchNearby(rescuerCoords.lat, rescuerCoords.lng);
      }
    } catch (err: any) {
      setToast({
        id: 'accept-fail',
        type: 'error',
        message: err.response?.data?.detail || 'This rescue was claimed by another responder or is closed.',
      });
      if (rescuerCoords) {
        syncLocationAndFetchNearby(rescuerCoords.lat, rescuerCoords.lng);
      }
    }
  };

  const handleStatusUpdate = async (newStatus: RescueStatus) => {
    if (!activeCase) return;

    try {
      const payload: any = {
        status: newStatus,
        notes: `Status updated to ${newStatus.replace(/_/g, ' ')} by responder`,
      };

      if (['TRANSPORTING', 'AT_VETERINARY_FACILITY'].includes(newStatus) && selectedFacilityId) {
        payload.veterinary_facility_id = selectedFacilityId;
      }

      const response = await api.patch(`/rescues/${activeCase.id}/status`, payload);
      setActiveCase(response.data);

      setToast({
        id: 'status-ok',
        type: 'success',
        message: `Status updated: ${newStatus.replace(/_/g, ' ')}`,
      });

      if (['AT_VETERINARY_FACILITY', 'CLOSED'].includes(newStatus)) {
        setActiveCase(null);
        if (rescuerCoords) {
          syncLocationAndFetchNearby(rescuerCoords.lat, rescuerCoords.lng);
        }
      }
    } catch (err: any) {
      setToast({
        id: 'status-fail',
        type: 'error',
        message: err.response?.data?.detail || 'Failed to update rescue status.',
      });
    }
  };

  const nextValidStatuses: Record<string, RescueStatus[]> = {
    'RESPONDER_ASSIGNED': ['RESPONDER_EN_ROUTE'],
    'RESPONDER_EN_ROUTE': ['ANIMAL_LOCATED'],
    'ANIMAL_LOCATED': ['RESCUED'],
    'RESCUED': ['TRANSPORTING'],
    'TRANSPORTING': ['AT_VETERINARY_FACILITY'],
  };

  if (loading && nearbyCases.length === 0 && !activeCase) {
    return (
      <div className="max-w-4xl mx-auto py-16 text-center">
        <div className="inline-block w-8 h-8 border-4 border-brand-teal border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-gray-600 font-medium">Synchronizing responder GPS & locating emergencies...</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Toast toast={toast} onClose={() => setToast(null)} />

      {/* Responder Status Banner */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center bg-brand-darkNavy text-white p-5 rounded-xl shadow-md gap-4">
        <div>
          <h1 className="text-xl font-bold flex items-center">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 mr-2.5 animate-pulse" />
            Responder Operations Dashboard
          </h1>
          <p className="text-gray-300 text-xs mt-1">
            Status: <span className="text-emerald-400 font-semibold">ONLINE & AVAILABLE</span>
            {rescuerCoords && (
              <span className="ml-3 text-gray-400">
                • GPS: {rescuerCoords.lat}, {rescuerCoords.lng}
              </span>
            )}
          </p>
        </div>

        <button
          type="button"
          onClick={detectLocation}
          disabled={locating}
          className="bg-white/10 hover:bg-white/20 border border-white/20 text-white text-xs font-semibold px-3 py-2 rounded-lg flex items-center transition-colors self-end sm:self-auto"
        >
          <Crosshair className={`w-3.5 h-3.5 mr-1.5 ${locating ? 'animate-spin' : ''}`} />
          {locating ? 'Updating GPS...' : 'Refresh GPS'}
        </button>
      </div>

      {/* Active Rescue Mission Section */}
      {activeCase ? (
        <div className="bg-white rounded-xl shadow-lg border-2 border-brand-teal overflow-hidden animate-in fade-in">
          <div className="bg-brand-softMint px-6 py-4 border-b border-brand-teal flex justify-between items-center">
            <h2 className="text-lg font-bold text-brand-darkNavy flex items-center">
              <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse mr-2" />
              Active Rescue Mission
            </h2>
            <span className="font-mono text-xs bg-white px-2.5 py-1 rounded font-bold border border-gray-200">
              {activeCase.case_number}
            </span>
          </div>

          <div className="p-6 space-y-6">
            <div className="grid md:grid-cols-2 gap-6">
              <div className="space-y-4">
                <div>
                  <h3 className="text-xs uppercase font-bold text-gray-400 tracking-wider">Animal Species</h3>
                  <p className="font-bold text-xl text-brand-darkNavy">{activeCase.species}</p>
                </div>

                <div>
                  <h3 className="text-xs uppercase font-bold text-gray-400 tracking-wider">Triage Reason</h3>
                  <p className="bg-orange-50 text-orange-800 p-3 rounded-lg text-sm mt-1 border border-orange-100 font-medium">
                    {activeCase.triage_reason}
                  </p>
                </div>

                {activeCase.images && activeCase.images.length > 0 && (
                  <div>
                    <h3 className="text-xs uppercase font-bold text-gray-400 tracking-wider mb-2">Reported Photo</h3>
                    <div className="h-32 w-48 rounded-lg overflow-hidden border border-gray-200 shadow-sm">
                      <img src={activeCase.images[0].image_url} alt="Animal" className="w-full h-full object-cover" />
                    </div>
                  </div>
                )}
              </div>

              <div className="space-y-3">
                <h3 className="text-xs uppercase font-bold text-gray-400 tracking-wider">Emergency Location</h3>
                <div className="flex items-start bg-gray-50 p-3 rounded-lg border border-gray-200 text-sm">
                  <MapPin className="w-4 h-4 text-brand-teal mr-2 flex-shrink-0 mt-0.5" />
                  <p className="font-medium text-gray-800">{activeCase.address_text}</p>
                </div>

                <MapView
                  lat={activeCase.latitude}
                  lng={activeCase.longitude}
                  title={`Rescue Case ${activeCase.case_number}`}
                  height="180px"
                />
              </div>
            </div>

            {/* Status Progression Controls */}
            <div className="border-t border-gray-100 pt-6">
              <div className="bg-gray-50 rounded-xl p-5 border border-gray-200 flex flex-col items-center">
                <span className="text-xs uppercase tracking-wider font-bold text-gray-400 mb-1">Current Mission Status</span>
                <span className="text-brand-teal font-extrabold text-xl mb-4 text-center">
                  {activeCase.status.replace(/_/g, ' ')}
                </span>

                {/* Veterinary Facility Selector for Transporting */}
                {['RESCUED', 'TRANSPORTING'].includes(activeCase.status) && (
                  <div className="w-full max-w-sm mb-4 bg-white p-3.5 rounded-lg border border-gray-200 shadow-sm">
                    <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1 flex items-center">
                      <Building2 className="w-3.5 h-3.5 mr-1 text-brand-teal" />
                      Select Veterinary Destination
                    </label>
                    <select
                      value={selectedFacilityId}
                      onChange={(e) => setSelectedFacilityId(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-teal"
                    >
                      {facilities.map((fac) => (
                        <option key={fac.id} value={fac.id}>
                          {fac.name} {fac.is_24_hours ? '(24/7)' : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="w-full max-w-sm space-y-3">
                  {(nextValidStatuses[activeCase.status] || []).map((nextStatus) => (
                    <button
                      key={nextStatus}
                      type="button"
                      onClick={() => handleStatusUpdate(nextStatus)}
                      className="w-full bg-brand-coral hover:bg-red-500 text-white font-bold py-3.5 px-4 rounded-xl shadow-md transition-all flex items-center justify-between"
                    >
                      <span>Mark as {nextStatus.replace(/_/g, ' ')}</span>
                      <ChevronRight className="w-5 h-5" />
                    </button>
                  ))}

                  {(!nextValidStatuses[activeCase.status] || nextValidStatuses[activeCase.status].length === 0) && (
                    <p className="text-gray-500 text-xs text-center font-medium">
                      Animal handed off to veterinary facility. Awaiting medical diagnosis and treatment.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Nearby Emergencies List */
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-bold text-brand-darkNavy flex items-center">
              Nearby Emergencies
              <span className="ml-2.5 bg-gray-100 text-gray-700 text-xs px-2.5 py-0.5 rounded-full font-semibold">
                {nearbyCases.length} available
              </span>
            </h2>
            <span className="text-xs text-gray-500">Sorted by Priority & Calculated Distance</span>
          </div>

          {nearbyCases.length === 0 ? (
            <div className="bg-white p-12 rounded-xl shadow-sm border border-gray-100 text-center">
              <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
              <h3 className="font-bold text-gray-800 text-lg">No Active Emergencies Nearby</h3>
              <p className="text-gray-500 text-sm mt-1">All reported animals in your operational radius are currently attended to.</p>
            </div>
          ) : (
            <div className="grid gap-4">
              {nearbyCases.map((rescue) => (
                <div
                  key={rescue.id}
                  className="bg-white p-5 rounded-xl shadow-sm border-l-4 border-l-brand-coral border border-gray-100 hover:shadow-md transition-all flex flex-col md:flex-row justify-between items-start md:items-center gap-4"
                >
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={`text-xs font-bold px-2.5 py-0.5 rounded tracking-wide ${
                          rescue.triage_priority === 'CRITICAL'
                            ? 'bg-red-100 text-red-800'
                            : rescue.triage_priority === 'URGENT'
                            ? 'bg-orange-100 text-orange-800'
                            : 'bg-blue-100 text-blue-800'
                        }`}
                      >
                        {rescue.triage_priority} PRIORITY
                      </span>
                      <span className="text-xs font-mono text-gray-400 font-semibold">{rescue.case_number}</span>
                      <span className="text-xs text-gray-400 flex items-center">
                        <Clock className="w-3.5 h-3.5 mr-1" />
                        {Math.round((Date.now() - new Date(rescue.created_at).getTime()) / 60000)} min ago
                      </span>
                    </div>

                    <h3 className="font-bold text-lg text-brand-darkNavy">{rescue.species} Rescue</h3>
                    <p className="text-gray-600 text-sm">{rescue.triage_reason}</p>

                    <div className="flex items-center text-xs font-medium text-gray-500 gap-4 pt-1">
                      <span className="flex items-center">
                        <MapPin className="w-3.5 h-3.5 mr-1 text-brand-teal" />
                        {rescue.address_text}
                      </span>
                      {rescue.distance_km !== undefined && (
                        <span className="bg-brand-softMint text-brand-teal px-2 py-0.5 rounded font-bold">
                          {rescue.distance_km} km away
                        </span>
                      )}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleAccept(rescue.id)}
                    className="w-full md:w-auto bg-brand-darkNavy hover:bg-brand-deepNavy text-white px-5 py-2.5 rounded-lg text-sm font-semibold shadow-sm transition-colors flex items-center justify-center flex-shrink-0"
                  >
                    Accept Rescue Mission
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
