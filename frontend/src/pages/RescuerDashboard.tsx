import { useEffect, useState, useCallback } from 'react';
import api from '../services/api';
import { formatApiError } from '../utils/error';
import type { RescueCase, RescueStatus, VeterinaryFacility, DispatchOffer } from '../types';
import {
  MapPin,
  Clock,
  ChevronRight,
  Crosshair,
  Building2,
  CheckCircle,
  AlertTriangle,
  ShieldAlert,
  XCircle,
  Navigation,
} from 'lucide-react';
import { MapView } from '../components/MapView';
import { Toast, type ToastMessage } from '../components/Toast';

const OfferCountdown = ({
  expiresAt,
  onExpired,
}: {
  expiresAt?: string;
  onExpired: () => void;
}) => {
  const [timeLeft, setTimeLeft] = useState<number>(0);

  useEffect(() => {
    if (!expiresAt) return;
    const calculateTime = () => {
      const diff = Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000));
      setTimeLeft(diff);
      if (diff <= 0) {
        onExpired();
      }
    };
    calculateTime();
    const interval = setInterval(calculateTime, 1000);
    return () => clearInterval(interval);
  }, [expiresAt, onExpired]);

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;
  const formatted = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

  return (
    <span
      id="offer-countdown-timer"
      className={`inline-flex items-center font-mono font-bold text-xs sm:text-sm px-2.5 py-1 rounded-md border ${
        timeLeft < 30
          ? 'bg-red-50 text-red-700 border-red-200 animate-pulse'
          : 'bg-amber-50 text-amber-800 border-amber-200'
      }`}
    >
      <Clock className="w-3.5 h-3.5 mr-1" />
      Expires in {formatted}
    </span>
  );
};

export const RescuerDashboard = () => {
  const [incomingOffers, setIncomingOffers] = useState<DispatchOffer[]>([]);
  const [nearbyCases, setNearbyCases] = useState<RescueCase[]>([]);
  const [activeCase, setActiveCase] = useState<RescueCase | null>(null);
  const [facilities, setFacilities] = useState<VeterinaryFacility[]>([]);
  const [selectedFacilityId, setSelectedFacilityId] = useState<string>('');

  const [loading, setLoading] = useState(true);
  const [rescuerCoords, setRescuerCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [locating, setLocating] = useState(false);
  const [toast, setToast] = useState<ToastMessage | null>(null);

  // Reject dialog state
  const [rejectingOfferId, setRejectingOfferId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState<string>('too_far');
  const [submittingAction, setSubmittingAction] = useState<string | null>(null);

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

  const fetchIncomingOffers = useCallback(async () => {
    try {
      const res = await api.get('/rescuers/me/offers');
      setIncomingOffers(res.data);
    } catch {
      // Background poll failure handled gracefully
    }
  }, []);

  const syncLocationAndFetchNearby = async (lat: number, lng: number) => {
    try {
      await api.patch('/rescuers/me/location', { latitude: lat, longitude: lng });

      const response = await api.get('/rescues/nearby', {
        params: { lat, lng, radius_km: 15.0 },
      });
      setNearbyCases(response.data);
    } catch (err: any) {
      setToast({
        id: 'nearby-err',
        type: 'error',
        message: formatApiError(err, 'Failed to fetch nearby emergencies.'),
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
          message: 'Location access denied. Using station coordinates.',
        });
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
    fetchIncomingOffers();

    const interval = setInterval(() => {
      fetchIncomingOffers();
      if (rescuerCoords) {
        syncLocationAndFetchNearby(rescuerCoords.lat, rescuerCoords.lng);
      }
    }, 8000);

    return () => clearInterval(interval);
  }, [fetchIncomingOffers]);

  const handleAcceptOffer = async (offerId: string) => {
    setSubmittingAction(offerId);
    try {
      const res = await api.post(`/rescuers/offers/${offerId}/accept`);
      setToast({
        id: 'offer-accepted',
        type: 'success',
        message: 'Dispatch offer accepted! Rescue assigned to you.',
      });
      // Load active case
      if (res.data.rescue_case_id) {
        const caseRes = await api.get(`/rescues/${res.data.rescue_case_id}`);
        setActiveCase(caseRes.data);
      }
      setIncomingOffers((prev) => prev.filter((o) => o.id !== offerId));
      if (rescuerCoords) {
        syncLocationAndFetchNearby(rescuerCoords.lat, rescuerCoords.lng);
      }
    } catch (err: any) {
      setToast({
        id: 'accept-fail',
        type: 'error',
        message: formatApiError(err, 'This offer expired or was claimed by another responder.'),
      });
      fetchIncomingOffers();
    } finally {
      setSubmittingAction(null);
    }
  };

  const handleRejectOffer = async () => {
    if (!rejectingOfferId) return;
    setSubmittingAction(rejectingOfferId);
    try {
      await api.post(`/rescuers/offers/${rejectingOfferId}/reject`, {
        reason: rejectReason,
      });
      setToast({
        id: 'offer-rejected',
        type: 'info',
        message: 'Rescue offer declined.',
      });
      setIncomingOffers((prev) => prev.filter((o) => o.id !== rejectingOfferId));
      setRejectingOfferId(null);
    } catch (err: any) {
      setToast({
        id: 'reject-fail',
        type: 'error',
        message: formatApiError(err, 'Failed to decline offer.'),
      });
    } finally {
      setSubmittingAction(null);
    }
  };

  const handleDirectAccept = async (caseId: string) => {
    setSubmittingAction(caseId);
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
        message: formatApiError(err, 'This rescue was claimed by another responder or is closed.'),
      });
      if (rescuerCoords) {
        syncLocationAndFetchNearby(rescuerCoords.lat, rescuerCoords.lng);
      }
    } finally {
      setSubmittingAction(null);
    }
  };

  const handleStatusUpdate = async (newStatus: RescueStatus) => {
    if (!activeCase) return;

    setSubmittingAction(newStatus);
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
        message: formatApiError(err, 'Failed to update rescue status.'),
      });
    } finally {
      setSubmittingAction(null);
    }
  };

  const nextValidStatuses: Record<string, RescueStatus[]> = {
    RESPONDER_ASSIGNED: ['RESPONDER_EN_ROUTE'],
    RESPONDER_EN_ROUTE: ['ANIMAL_LOCATED'],
    ANIMAL_LOCATED: ['RESCUED'],
    RESCUED: ['TRANSPORTING'],
    TRANSPORTING: ['AT_VETERINARY_FACILITY'],
  };

  if (loading && nearbyCases.length === 0 && !activeCase && incomingOffers.length === 0) {
    return (
      <div className="max-w-4xl mx-auto py-16 text-center">
        <div className="inline-block w-8 h-8 border-4 border-brand-teal border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-gray-600 font-medium">Synchronizing responder dispatch & GPS...</p>
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

      {/* SECTION: Incoming Dispatch Alerts */}
      {incomingOffers.length > 0 && (
        <div id="incoming-dispatch-alerts" className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
            </span>
            <h2 className="text-lg font-bold text-stone-900 tracking-tight">
              Incoming Rescue Alerts ({incomingOffers.length})
            </h2>
          </div>

          <div className="grid gap-4">
            {incomingOffers.map((offer) => {
              const c = offer.case;
              const isCritical = c?.triage_priority === 'CRITICAL';
              return (
                <div
                  key={offer.id}
                  id={`dispatch-offer-${offer.id}`}
                  className={`p-5 rounded-2xl border-2 transition-all shadow-md bg-white ${
                    isCritical
                      ? 'border-red-500 ring-2 ring-red-100'
                      : 'border-amber-400'
                  }`}
                >
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pb-3 border-b border-stone-100">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={`text-xs font-black px-2.5 py-1 rounded-full uppercase tracking-wider flex items-center gap-1 ${
                          isCritical
                            ? 'bg-red-600 text-white animate-pulse'
                            : 'bg-amber-100 text-amber-900'
                        }`}
                      >
                        <ShieldAlert className="w-3.5 h-3.5" />
                        {c?.triage_priority || 'EMERGENCY'} ALERT
                      </span>
                      <span className="text-xs font-mono font-bold text-stone-600 bg-stone-100 px-2 py-0.5 rounded">
                        {c?.case_number}
                      </span>
                      {offer.distance_km !== undefined && (
                        <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200 flex items-center gap-1">
                          <Navigation className="w-3 h-3" />
                          {offer.distance_km} km away
                        </span>
                      )}
                    </div>

                    <OfferCountdown
                      expiresAt={offer.expires_at}
                      onExpired={() => fetchIncomingOffers()}
                    />
                  </div>

                  <div className="py-4 space-y-2">
                    <div className="flex items-baseline justify-between">
                      <h3 className="text-lg font-extrabold text-stone-900">
                        {c?.species || 'Animal'} in Distress
                      </h3>
                      {offer.dispatch_score && (
                        <span className="text-xs font-semibold text-stone-500">
                          Match Score: <span className="text-stone-800 font-bold">{offer.dispatch_score}%</span>
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-stone-700 bg-stone-50 p-3 rounded-xl border border-stone-200/60 font-medium">
                      {c?.triage_reason || c?.description || 'Emergency intervention required.'}
                    </p>
                    <div className="flex items-center text-xs text-stone-500 pt-1">
                      <MapPin className="w-3.5 h-3.5 mr-1 text-red-500 shrink-0" />
                      <span className="truncate">{c?.address_text || 'Location captured via GPS'}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col sm:flex-row gap-2.5 pt-2">
                    <button
                      id={`accept-offer-btn-${offer.id}`}
                      onClick={() => handleAcceptOffer(offer.id)}
                      disabled={!!submittingAction}
                      className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 px-4 rounded-xl shadow transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      <CheckCircle className="w-4 h-4" />
                      {submittingAction === offer.id ? 'Accepting...' : 'Accept Rescue'}
                    </button>
                    <button
                      id={`decline-offer-btn-${offer.id}`}
                      onClick={() => setRejectingOfferId(offer.id)}
                      disabled={!!submittingAction}
                      className="px-4 py-3 border border-stone-300 hover:bg-stone-100 text-stone-700 font-semibold rounded-xl transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50"
                    >
                      <XCircle className="w-4 h-4 text-stone-400" />
                      Decline
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Decline Reason Modal */}
      {rejectingOfferId && (
        <div className="fixed inset-0 z-50 bg-stone-900/50 flex items-center justify-center p-4 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-stone-200">
            <h3 className="text-base font-bold text-stone-900 mb-2 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-500" />
              Decline Rescue Offer
            </h3>
            <p className="text-xs text-stone-600 mb-4">
              Help us re-route this emergency quickly by specifying why you cannot respond:
            </p>

            <div className="space-y-2 mb-5">
              {[
                { id: 'too_far', label: 'Too far away' },
                { id: 'already_busy', label: 'Already attending another rescue' },
                { id: 'vehicle_unavailable', label: 'Vehicle or transport unavailable' },
                { id: 'unsafe_conditions', label: 'Unsafe conditions / terrain' },
                { id: 'other', label: 'Other operational constraint' },
              ].map((r) => (
                <label
                  key={r.id}
                  className={`flex items-center p-2.5 rounded-lg border cursor-pointer text-xs font-medium transition-colors ${
                    rejectReason === r.id
                      ? 'bg-amber-50 border-amber-400 text-amber-900'
                      : 'border-stone-200 hover:bg-stone-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="rejectReason"
                    value={r.id}
                    checked={rejectReason === r.id}
                    onChange={(e) => setRejectReason(e.target.value)}
                    className="mr-2 text-amber-600 focus:ring-amber-500"
                  />
                  {r.label}
                </label>
              ))}
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleRejectOffer}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-2.5 px-4 rounded-xl text-xs transition-colors"
              >
                Confirm Decline
              </button>
              <button
                onClick={() => setRejectingOfferId(null)}
                className="px-4 py-2.5 border border-stone-300 hover:bg-stone-100 text-stone-700 font-semibold rounded-xl text-xs"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

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
                      disabled={!!submittingAction}
                      className="w-full bg-brand-coral hover:bg-red-500 text-white font-bold py-3.5 px-4 rounded-xl shadow-md transition-all flex items-center justify-between disabled:opacity-50"
                    >
                      <span>{submittingAction === nextStatus ? 'Updating Status...' : `Mark as ${nextStatus.replace(/_/g, ' ')}`}</span>
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
                    onClick={() => handleDirectAccept(rescue.id)}
                    disabled={!!submittingAction}
                    className="w-full md:w-auto bg-brand-darkNavy hover:bg-brand-deepNavy text-white px-5 py-2.5 rounded-lg text-sm font-semibold shadow-sm transition-colors flex items-center justify-center flex-shrink-0 disabled:opacity-50"
                  >
                    {submittingAction === rescue.id ? 'Claiming Mission...' : 'Accept Rescue Mission'}
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
