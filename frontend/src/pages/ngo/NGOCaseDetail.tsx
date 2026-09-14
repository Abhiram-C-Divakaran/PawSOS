import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  MapPin,
  ShieldAlert,
  Building2,
  Users,
  History,
  AlertOctagon,
  RefreshCw,
} from 'lucide-react';
import api from '../../services/api';
import { formatApiError } from '../../utils/error';
import { MapView } from '../../components/MapView';
import { Toast, type ToastMessage } from '../../components/Toast';
import { ProtectedImage } from '../../components/ProtectedImage';
import type { NGOResponderSummary, VeterinaryFacility } from '../../types';

export const NGOCaseDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastMessage | null>(null);

  // Administrative action modal state
  const [actionType, setActionType] = useState<string | null>(null);
  const [actionReason, setActionReason] = useState('');
  const [selectedRescuerId, setSelectedRescuerId] = useState<string>('');
  const [selectedFacilityId, setSelectedFacilityId] = useState<string>('');
  const [respondersList, setRespondersList] = useState<NGOResponderSummary[]>([]);
  const [facilitiesList, setFacilitiesList] = useState<VeterinaryFacility[]>([]);
  const [executingAction, setExecutingAction] = useState(false);

  const fetchDossier = useCallback(async () => {
    if (!id) return;
    try {
      const res = await api.get(`/ngo/cases/${id}`);
      setCaseData(res.data);
    } catch (err: any) {
      setToast({
        id: 'dossier-err',
        type: 'error',
        message: formatApiError(err, 'Failed to load case dossier.'),
      });
    } finally {
      setLoading(false);
    }
  }, [id]);

  const loadActionPrerequisites = useCallback(async () => {
    try {
      const [respRes, facRes] = await Promise.all([
        api.get('/ngo/responders').catch(() => ({ data: [] })),
        api.get('/ngo/veterinary').catch(() => ({ data: [] })),
      ]);
      setRespondersList(respRes.data || []);
      setFacilitiesList(facRes.data || []);
      if (respRes.data?.length > 0) setSelectedRescuerId(respRes.data[0].user_id);
      if (facRes.data?.length > 0) setSelectedFacilityId(facRes.data[0].id);
    } catch (err) {
      console.error('Failed to load action prerequisites', err);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    const init = async () => {
      if (mounted) {
        await fetchDossier();
        await loadActionPrerequisites();
      }
    };
    void init();
    return () => {
      mounted = false;
    };
  }, [fetchDossier, loadActionPrerequisites]);

  const handleExecuteAction = async () => {
    if (!actionType) return;
    try {
      setExecutingAction(true);
      const payload: any = {
        action: actionType,
        reason: actionReason || 'Administrative override from NGO Command Center',
      };
      if (actionType === 'assign_responder') {
        payload.rescuer_id = selectedRescuerId;
        payload.target_id = selectedRescuerId;
      } else if (actionType === 'change_facility') {
        payload.veterinary_facility_id = selectedFacilityId;
        payload.target_id = selectedFacilityId;
      }

      const res = await api.post(`/ngo/cases/${id}/actions`, payload);
      setToast({
        id: 'action-ok',
        type: 'success',
        message: res.data.message || 'Action executed successfully.',
      });
      setActionType(null);
      setActionReason('');
      fetchDossier();
    } catch (err: any) {
      setToast({
        id: 'action-fail',
        type: 'error',
        message: formatApiError(err, 'Failed to execute administrative action.'),
      });
    } finally {
      setExecutingAction(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center">
        <div className="inline-block w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-slate-600 font-medium text-sm">Loading complete rescue dossier...</p>
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="py-12 px-4 max-w-lg mx-auto text-center space-y-4">
        <Toast toast={toast} onClose={() => setToast(null)} />
        <div id="case-error-state" className="p-6 bg-red-50 border border-red-200 rounded-2xl text-red-700">
          <AlertOctagon className="w-10 h-10 mx-auto mb-2 text-red-500" />
          <h2 className="text-base font-bold">Access Denied or Case Not Found</h2>
          <p className="text-xs text-red-600 mt-1">
            This rescue case may belong to another organization or does not exist.
          </p>
        </div>
        <button
          onClick={() => navigate('/ngo/cases')}
          className="px-4 py-2 bg-slate-800 text-white rounded-xl text-xs font-semibold hover:bg-slate-700 transition"
        >
          Back to Organization Cases
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Toast toast={toast} onClose={() => setToast(null)} />

      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-sm">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/ngo/cases')}
            className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors"
            title="Back to Cases"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-slate-500">{caseData.case_number}</span>
              <span
                className={`text-[10px] font-black px-2 py-0.5 rounded-full uppercase ${
                  caseData.triage_priority === 'CRITICAL' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-800'
                }`}
              >
                {caseData.triage_priority}
              </span>
              <span
                data-testid="case-status-badge"
                className={`text-[10px] font-black px-2 py-0.5 rounded-full uppercase ${
                  caseData.status === 'UNRESOLVED'
                    ? 'bg-red-100 text-red-800'
                    : caseData.status === 'CLOSED'
                    ? 'bg-emerald-100 text-emerald-800'
                    : caseData.status === 'RESPONDER_ASSIGNED'
                    ? 'bg-teal-100 text-teal-800'
                    : 'bg-blue-100 text-blue-800'
                }`}
              >
                {caseData.status}
              </span>
            </div>
            <h1 className="text-xl font-black text-[#12213A] mt-0.5">
              {caseData.species} Emergency Dossier
            </h1>
          </div>
        </div>

        {/* Administrative Action Trigger */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setActionType('re_dispatch')}
            className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl text-xs flex items-center gap-1.5 shadow transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Re-Dispatch
          </button>
          <button
            onClick={() => setActionType('assign_responder')}
            className="px-3 py-2 border border-slate-300 hover:bg-slate-50 text-slate-800 font-bold rounded-xl text-xs flex items-center gap-1.5 transition-colors"
          >
            <Users className="w-3.5 h-3.5 text-slate-500" /> Manual Assign
          </button>
          <button
            onClick={() => setActionType('change_facility')}
            className="px-3 py-2 border border-slate-300 hover:bg-slate-50 text-slate-800 font-bold rounded-xl text-xs flex items-center gap-1.5 transition-colors"
          >
            <Building2 className="w-3.5 h-3.5 text-slate-500" /> Transfer Clinic
          </button>
          <button
            onClick={() => setActionType('cancel')}
            className="px-3 py-2 bg-red-50 hover:bg-red-100 text-red-700 font-bold rounded-xl text-xs flex items-center gap-1.5 border border-red-200 transition-colors"
          >
            <AlertOctagon className="w-3.5 h-3.5" /> Cancel Case
          </button>
        </div>
      </div>

      {/* Grid: Case Summary + Live Map */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-2xl border border-[#E4EAF2] p-6 shadow-sm space-y-5">
          <h2 className="text-sm font-bold text-[#12213A] uppercase tracking-wider border-b border-slate-100 pb-3">
            Triage & Scene Intelligence
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <span className="text-xs text-slate-400 font-semibold uppercase">Triage Evaluation</span>
              <p className="text-[#12213A] font-bold text-base mt-1">
                Score: {caseData.triage_score}/100 ({caseData.triage_priority})
              </p>
              <p className="text-xs text-slate-600 mt-1 bg-slate-50 p-3 rounded-xl border border-slate-100">
                {caseData.triage_reason || caseData.description}
              </p>
            </div>

            <div>
              <span className="text-xs text-slate-400 font-semibold uppercase">Reported Location</span>
              <p className="text-[#12213A] font-bold text-xs mt-1 flex items-start gap-1">
                <MapPin className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                {caseData.address_text || 'GPS Location'}
              </p>
              <div className="mt-2 text-[11px] text-slate-400 font-mono">
                Coordinates: {caseData.latitude}, {caseData.longitude}
              </div>
            </div>
          </div>

          {caseData.images && caseData.images.length > 0 && (
            <div>
              <span className="text-xs text-slate-400 font-semibold uppercase mb-2 block">Incident Photo</span>
              <div className="h-44 w-64 rounded-xl overflow-hidden border border-slate-200 shadow-sm">
                <ProtectedImage
                  caseId={caseData.id}
                  imageId={caseData.images[0].id}
                  src={caseData.images[0].image_url}
                  alt="Animal"
                  className="w-full h-full object-cover"
                />
              </div>
            </div>
          )}
        </div>

        {/* Map */}
        <div className="bg-white rounded-2xl border border-[#E4EAF2] p-4 shadow-sm flex flex-col">
          <h3 className="text-xs font-bold text-[#12213A] uppercase tracking-wider mb-3">Geographic Fix</h3>
          <div className="flex-1 min-h-[220px]">
            <MapView
              lat={caseData.latitude}
              lng={caseData.longitude}
              title={`Rescue #${caseData.case_number}`}
              height="100%"
            />
          </div>
        </div>
      </div>

      {/* Dispatch History & Responders Offered */}
      <div className="bg-white rounded-2xl border border-[#E4EAF2] p-6 shadow-sm space-y-4">
        <h2 className="text-sm font-bold text-[#12213A] uppercase tracking-wider flex items-center gap-2 border-b border-slate-100 pb-3">
          <ShieldAlert className="w-4 h-4 text-amber-600" /> Automatic Dispatch Offer Trail
        </h2>

        {caseData.dispatch_offers && caseData.dispatch_offers.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[10px] font-bold uppercase text-slate-500 border-b border-[#E4EAF2]">
                  <th className="py-2.5 px-3">Responder</th>
                  <th className="py-2.5 px-3">Match Score</th>
                  <th className="py-2.5 px-3">Distance</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Offered At</th>
                  <th className="py-2.5 px-3">Notes / Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {caseData.dispatch_offers.map((offer: any) => (
                  <tr key={offer.id}>
                    <td className="py-2.5 px-3 font-semibold text-slate-900">{offer.rescuer_name}</td>
                    <td className="py-2.5 px-3 font-bold text-blue-700">{offer.dispatch_score}%</td>
                    <td className="py-2.5 px-3 text-slate-600">{offer.distance_km} km</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                          offer.status === 'ACCEPTED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : offer.status === 'PENDING'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {offer.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      {offer.offered_at ? new Date(offer.offered_at).toLocaleTimeString() : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-500 italic">{offer.rejection_reason || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-slate-400 py-3">No dispatch offers recorded yet.</p>
        )}
      </div>

      {/* Audit Trail Log */}
      <div className="bg-white rounded-2xl border border-[#E4EAF2] p-6 shadow-sm space-y-4">
        <h2 className="text-sm font-bold text-[#12213A] uppercase tracking-wider flex items-center gap-2 border-b border-slate-100 pb-3">
          <History className="w-4 h-4 text-blue-600" /> Administrative Audit Trail
        </h2>

        {caseData.audit_trail && caseData.audit_trail.length > 0 ? (
          <div className="space-y-2">
            {caseData.audit_trail.map((log: any) => (
              <div key={log.id} className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-xs flex justify-between items-center">
                <div>
                  <span className="font-bold text-slate-900">{log.action}</span>
                  <span className="text-slate-500 ml-2">
                    {log.new_value?.reason ? `(Reason: ${log.new_value.reason})` : ''}
                  </span>
                </div>
                <span className="text-[11px] text-slate-400">
                  {new Date(log.timestamp).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-400 py-2">No administrative overrides logged on this case.</p>
        )}
      </div>

      {/* Administrative Action Modal */}
      {actionType && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 flex items-center justify-center p-4 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-[#E4EAF2] space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <h3 className="text-base font-bold text-[#12213A]">
              Confirm Action: {actionType.toUpperCase().replace(/_/g, ' ')}
            </h3>

            {actionType === 'assign_responder' && (
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Select Field Responder:</label>
                <select
                  value={selectedRescuerId}
                  onChange={(e) => setSelectedRescuerId(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs bg-white focus:ring-2 focus:ring-blue-500"
                >
                  {respondersList.map((r) => (
                    <option key={r.user_id} value={r.user_id}>
                      {r.full_name} ({r.availability_status} - {r.experience_level})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {actionType === 'change_facility' && (
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Select Partner Clinic:</label>
                <select
                  value={selectedFacilityId}
                  onChange={(e) => setSelectedFacilityId(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs bg-white focus:ring-2 focus:ring-blue-500"
                >
                  {facilitiesList.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name} {f.is_24_hours ? '(24/7)' : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Operational Audit Reason:</label>
              <textarea
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                placeholder="Specify reason for audit logging..."
                className="w-full p-3 border border-slate-300 rounded-xl text-xs focus:ring-2 focus:ring-blue-500 focus:outline-none"
                rows={3}
              />
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={handleExecuteAction}
                disabled={executingAction}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-bold py-2.5 rounded-xl text-xs transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                {executingAction ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Executing...
                  </>
                ) : (
                  'Execute & Audit Log'
                )}
              </button>
              <button
                onClick={() => setActionType(null)}
                className="px-4 py-2.5 border border-slate-300 hover:bg-slate-100 text-slate-700 font-semibold rounded-xl text-xs"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
