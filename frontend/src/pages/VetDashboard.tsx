import { useEffect, useState } from 'react';
import api from '../services/api';
import { formatApiError } from '../utils/error';
import type { RescueCase, RescueStatus, VeterinaryFacility } from '../types';
import { Stethoscope, PlusCircle, CheckCircle, HeartPulse } from 'lucide-react';
import { Toast, type ToastMessage } from '../components/Toast';

export const VetDashboard = () => {
  const [cases, setCases] = useState<RescueCase[]>([]);
  const [selectedCase, setSelectedCase] = useState<RescueCase | null>(null);
  const [facilities, setFacilities] = useState<VeterinaryFacility[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastMessage | null>(null);

  // Treatment Form State
  const [diagnosis, setDiagnosis] = useState('');
  const [notes, setNotes] = useState('');
  const [medications, setMedications] = useState('');
  const [facilityId, setFacilityId] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchFacilities = async () => {
    try {
      const res = await api.get('/veterinary/facilities');
      setFacilities(res.data);
      if (res.data.length > 0) {
        setFacilityId(res.data[0].id);
      }
    } catch (err) {
      console.error('Failed to load facilities', err);
    }
  };

  const fetchCases = async () => {
    try {
      // Dedicated veterinary inbox endpoint
      const response = await api.get('/veterinary/cases');
      setCases(response.data);
    } catch (err: any) {
      setToast({
        id: 'vet-cases-err',
        type: 'error',
        message: formatApiError(err, 'Failed to load veterinary inbox cases.'),
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFacilities();
    fetchCases();
    const interval = setInterval(fetchCases, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectCase = (c: RescueCase) => {
    setSelectedCase(c);
    if (c.veterinary_facility_id) {
      setFacilityId(c.veterinary_facility_id);
    } else if (facilities.length > 0) {
      setFacilityId(facilities[0].id);
    }
  };

  const handleTreatmentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCase) return;

    if (!facilityId) {
      setToast({
        id: 'no-fac',
        type: 'warning',
        message: 'Please select an admitting veterinary facility.',
      });
      return;
    }

    setSubmitting(true);
    try {
      // Record medical treatment with consistent types
      await api.post(`/rescues/${selectedCase.id}/treatments`, {
        diagnosis,
        treatment_notes: notes,
        medications: medications || null,
        facility_id: facilityId,
        recovery_status: 'In Treatment',
      });

      setToast({
        id: 'treatment-saved',
        type: 'success',
        message: `Medical assessment and treatment recorded for ${selectedCase.case_number}.`,
      });

      setDiagnosis('');
      setNotes('');
      setMedications('');
      setSelectedCase(null);
      fetchCases();
    } catch (err: any) {
      setToast({
        id: 'treatment-err',
        type: 'error',
        message: formatApiError(err, 'Failed to submit treatment record.'),
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleAdvanceStatus = async (targetStatus: RescueStatus) => {
    if (!selectedCase) return;

    setSubmitting(true);
    try {
      await api.patch(`/rescues/${selectedCase.id}/status`, {
        status: targetStatus,
        notes: `Progressed by veterinary staff to ${targetStatus.replace(/_/g, ' ')}`,
      });

      setToast({
        id: 'adv-status-ok',
        type: 'success',
        message: `Case status advanced to ${targetStatus.replace(/_/g, ' ')}.`,
      });

      setSelectedCase(null);
      fetchCases();
    } catch (err: any) {
      setToast({
        id: 'adv-status-err',
        type: 'error',
        message: formatApiError(err, 'Failed to advance case status.'),
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading && cases.length === 0) {
    return (
      <div className="max-w-6xl mx-auto py-16 text-center">
        <div className="inline-block w-8 h-8 border-4 border-brand-teal border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-gray-600 font-medium">Loading veterinary inpatient registry...</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <Toast toast={toast} onClose={() => setToast(null)} />

      <div className="flex justify-between items-center bg-brand-darkNavy text-white p-5 rounded-xl shadow-md">
        <div>
          <h1 className="text-xl font-bold flex items-center">
            <Stethoscope className="w-5 h-5 mr-2.5 text-brand-teal" />
            Veterinary Care & Clinical Inpatient Registry
          </h1>
          <p className="text-gray-300 text-xs mt-1">
            Review arriving rescue cases, confirm veterinary diagnoses, and log patient recovery.
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Cases List */}
        <div className="lg:col-span-1 space-y-4">
          <h2 className="font-bold text-gray-800 text-base flex items-center justify-between">
            <span>Inpatient Cases</span>
            <span className="bg-gray-100 text-gray-700 text-xs px-2.5 py-0.5 rounded-full font-semibold">
              {cases.length} active
            </span>
          </h2>

          {cases.length === 0 ? (
            <div className="bg-white p-8 rounded-xl border border-gray-200 text-center text-gray-500">
              <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
              <p className="text-sm font-medium">No rescue cases currently awaiting veterinary care.</p>
            </div>
          ) : (
            cases.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => handleSelectCase(c)}
                className={`w-full text-left p-4 rounded-xl border-2 transition-all shadow-sm ${
                  selectedCase?.id === c.id
                    ? 'border-brand-teal bg-brand-softMint'
                    : 'border-gray-100 bg-white hover:border-gray-300'
                }`}
              >
                <div className="flex justify-between items-start mb-1.5">
                  <span className="font-mono font-bold text-brand-darkNavy text-sm">{c.case_number}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded font-bold ${
                      c.status === 'AT_VETERINARY_FACILITY'
                        ? 'bg-amber-100 text-amber-800'
                        : c.status === 'UNDER_TREATMENT'
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-emerald-100 text-emerald-800'
                    }`}
                  >
                    {c.status.replace(/_/g, ' ')}
                  </span>
                </div>
                <p className="font-semibold text-gray-800 text-sm">{c.species} Rescue</p>
                <p className="text-xs text-gray-500 line-clamp-1 mt-0.5">{c.triage_reason}</p>
              </button>
            ))
          )}
        </div>

        {/* Selected Case / Treatment Form */}
        <div className="lg:col-span-2">
          {selectedCase ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden animate-in fade-in">
              <div className="bg-gray-50 px-6 py-4 border-b border-gray-200 flex justify-between items-center">
                <h2 className="text-base font-bold text-brand-darkNavy">
                  Medical Record: {selectedCase.case_number} ({selectedCase.species})
                </h2>
                <span className="text-xs font-semibold text-brand-teal bg-teal-50 px-2.5 py-1 rounded border border-teal-200">
                  Status: {selectedCase.status.replace(/_/g, ' ')}
                </span>
              </div>

              <div className="p-6 space-y-6">
                {/* Triage summary & photo */}
                <div className="grid sm:grid-cols-3 gap-4">
                  <div className="sm:col-span-2 bg-orange-50 p-4 rounded-xl border border-orange-100">
                    <h3 className="text-xs font-bold text-orange-900 uppercase mb-1">Reported Condition (Citizen Triage)</h3>
                    <p className="text-sm text-orange-800 font-medium">{selectedCase.triage_reason}</p>
                    {selectedCase.description && (
                      <p className="text-xs text-orange-700 mt-2 italic">"{selectedCase.description}"</p>
                    )}
                  </div>

                  {selectedCase.images && selectedCase.images.length > 0 ? (
                    <div className="h-28 rounded-xl overflow-hidden border border-gray-200">
                      <img src={selectedCase.images[0].image_url} alt="Animal" className="w-full h-full object-cover" />
                    </div>
                  ) : (
                    <div className="h-28 rounded-xl bg-gray-50 border border-dashed border-gray-300 flex items-center justify-center text-gray-400 text-xs">
                      No photo
                    </div>
                  )}
                </div>

                {/* Treatment Form */}
                <form onSubmit={handleTreatmentSubmit} className="space-y-4">
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                        Admitting Facility
                      </label>
                      <select
                        value={facilityId}
                        onChange={(e) => setFacilityId(e.target.value)}
                        className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-teal"
                        required
                      >
                        {facilities.map((fac) => (
                          <option key={fac.id} value={fac.id}>
                            {fac.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                        Veterinary Diagnosis *
                      </label>
                      <input
                        type="text"
                        required
                        value={diagnosis}
                        onChange={(e) => setDiagnosis(e.target.value)}
                        placeholder="e.g. Femur fracture, dehydration, laceration"
                        className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-teal"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                      Prescribed Medications (comma separated)
                    </label>
                    <input
                      type="text"
                      value={medications}
                      onChange={(e) => setMedications(e.target.value)}
                      placeholder="e.g. Meloxicam 0.2mg/kg, Amoxicillin-Clavulanate 12.5mg/kg"
                      className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-teal"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                      Clinical Notes & Treatment Plan *
                    </label>
                    <textarea
                      required
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={3}
                      className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-teal"
                      placeholder="Enter examination findings, wound dressing, splint application, fluids given..."
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full bg-brand-teal hover:bg-brand-brightTeal text-white font-bold py-3 px-4 rounded-lg shadow transition-colors flex justify-center items-center text-sm disabled:opacity-50"
                  >
                    {submitting ? (
                      'Saving Clinical Record...'
                    ) : (
                      <>
                        <PlusCircle className="w-4 h-4 mr-2" />
                        Log Medical Assessment & Start Treatment
                      </>
                    )}
                  </button>
                </form>

                {/* Patient Recovery Progression Controls */}
                {selectedCase.status === 'UNDER_TREATMENT' && (
                  <div className="border-t border-gray-100 pt-5 space-y-3">
                    <h3 className="text-xs uppercase font-bold text-gray-500 tracking-wider">
                      Patient Recovery Progression
                    </h3>
                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => handleAdvanceStatus('RECOVERING')}
                        disabled={submitting}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold px-4 py-2.5 rounded-lg shadow-sm transition-colors flex items-center disabled:opacity-50"
                      >
                        <HeartPulse className="w-3.5 h-3.5 mr-1.5" />
                        {submitting ? 'Updating...' : 'Mark as Recovering'}
                      </button>
                    </div>
                  </div>
                )}

                {selectedCase.status === 'RECOVERING' && (
                  <div className="border-t border-gray-100 pt-5 space-y-3">
                    <h3 className="text-xs uppercase font-bold text-gray-500 tracking-wider">
                      Discharge & Placement Status
                    </h3>
                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => handleAdvanceStatus('READY_FOR_RELEASE')}
                        disabled={submitting}
                        className="bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold px-4 py-2.5 rounded-lg shadow-sm transition-colors disabled:opacity-50"
                      >
                        {submitting ? 'Updating...' : 'Ready for Release'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleAdvanceStatus('READY_FOR_ADOPTION')}
                        disabled={submitting}
                        className="bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold px-4 py-2.5 rounded-lg shadow-sm transition-colors disabled:opacity-50"
                      >
                        {submitting ? 'Updating...' : 'Ready for Adoption'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleAdvanceStatus('CLOSED')}
                        disabled={submitting}
                        className="bg-gray-800 hover:bg-gray-900 text-white text-xs font-bold px-4 py-2.5 rounded-lg shadow-sm transition-colors disabled:opacity-50"
                      >
                        {submitting ? 'Updating...' : 'Close Case'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-gray-50 h-full min-h-[360px] rounded-xl border-2 border-dashed border-gray-200 flex flex-col items-center justify-center p-8 text-center">
              <Stethoscope className="w-12 h-12 text-gray-300 mb-3" />
              <h3 className="text-base font-bold text-gray-600">Select an Inpatient Case</h3>
              <p className="text-xs text-gray-400 mt-1 max-w-sm">
                Choose an admitted animal from the list on the left to review triage signs and record medical treatment.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
