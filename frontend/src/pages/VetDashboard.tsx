import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { RescueCase, RescueStatus } from '../types';
import { MapPin, Clock, Syringe, PlusCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const VetDashboard = () => {
  const [cases, setCases] = useState<RescueCase[]>([]);
  const [selectedCase, setSelectedCase] = useState<RescueCase | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Treatment Form State
  const [diagnosis, setDiagnosis] = useState('');
  const [notes, setNotes] = useState('');
  const [medications, setMedications] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchCases = async () => {
    try {
      // In a real app, this would be a specific endpoint for the vet's facility
      // For MVP, we'll fetch nearby/all and filter to AT_VETERINARY_FACILITY or UNDER_TREATMENT
      const response = await api.get('/rescues/nearby'); 
      const vetCases = response.data.filter((c: RescueCase) => 
        ['AT_VETERINARY_FACILITY', 'UNDER_TREATMENT'].includes(c.status)
      );
      setCases(vetCases);
    } catch (err) {
      console.error('Failed to load vet cases', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, []);

  const handleTreatmentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCase) return;
    setSubmitting(true);
    
    try {
      // 1. Submit treatment record
      await api.post(`/rescues/${selectedCase.id}/treatments`, {
        diagnosis,
        treatment_notes: notes,
        medications: medications ? medications.split(',').map(m => m.trim()) : [],
        treatment_start: new Date().toISOString()
      });

      // 2. Update status to UNDER_TREATMENT or RECOVERING
      await api.patch(`/rescues/${selectedCase.id}/status`, {
        status: 'UNDER_TREATMENT',
        notes: `Treatment started: ${diagnosis}`
      });

      alert('Treatment recorded successfully.');
      setSelectedCase(null);
      setDiagnosis('');
      setNotes('');
      setMedications('');
      fetchCases();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to submit treatment.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="text-center py-12">Loading cases...</div>;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-brand-darkNavy">Veterinary Dashboard</h1>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Cases List */}
        <div className="lg:col-span-1 space-y-4">
          <h2 className="font-semibold text-gray-700 flex items-center">
            <Syringe className="w-5 h-5 mr-2" /> Incoming & Active Cases
          </h2>
          
          {cases.length === 0 ? (
            <div className="bg-white p-6 rounded-lg border border-gray-200 text-center text-gray-500">
              No cases currently assigned to your facility.
            </div>
          ) : (
            cases.map(c => (
              <button
                key={c.id}
                onClick={() => setSelectedCase(c)}
                className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
                  selectedCase?.id === c.id 
                    ? 'border-brand-teal bg-brand-softMint' 
                    : 'border-gray-100 bg-white hover:border-gray-300'
                }`}
              >
                <div className="flex justify-between items-start mb-2">
                  <span className="font-bold text-brand-darkNavy">{c.case_number}</span>
                  <span className={`text-xs px-2 py-1 rounded font-bold ${
                    c.status === 'AT_VETERINARY_FACILITY' ? 'bg-orange-100 text-orange-800' : 'bg-blue-100 text-blue-800'
                  }`}>
                    {c.status === 'AT_VETERINARY_FACILITY' ? 'Just Arrived' : 'In Treatment'}
                  </span>
                </div>
                <p className="font-medium text-gray-800 mb-1">{c.species}</p>
                <p className="text-xs text-gray-500 line-clamp-1">{c.triage_reason}</p>
              </button>
            ))
          )}
        </div>

        {/* Selected Case / Treatment Form */}
        <div className="lg:col-span-2">
          {selectedCase ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
                <h2 className="text-lg font-bold text-brand-darkNavy">Medical Assessment: {selectedCase.case_number}</h2>
              </div>
              
              <div className="p-6">
                <div className="bg-red-50 p-4 rounded-lg mb-6 border border-red-100">
                  <h3 className="text-sm font-bold text-red-800 mb-1">Reported Condition (Triage)</h3>
                  <p className="text-sm text-red-700">{selectedCase.triage_reason}</p>
                  {selectedCase.description && (
                    <p className="text-sm text-red-700 mt-2 italic">"{selectedCase.description}"</p>
                  )}
                </div>

                <form onSubmit={handleTreatmentSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Veterinary Diagnosis</label>
                    <input
                      type="text"
                      required
                      value={diagnosis}
                      onChange={(e) => setDiagnosis(e.target.value)}
                      placeholder="e.g. Femur fracture, severe dehydration"
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Medications (comma separated)</label>
                    <input
                      type="text"
                      value={medications}
                      onChange={(e) => setMedications(e.target.value)}
                      placeholder="e.g. Meloxicam, Cephalexin"
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Treatment Notes & Plan</label>
                    <textarea
                      required
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={4}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal"
                      placeholder="Detailed medical notes..."
                    />
                  </div>
                  <div className="pt-4">
                    <button
                      type="submit"
                      disabled={submitting}
                      className="w-full bg-brand-teal hover:bg-brand-brightTeal text-white font-bold py-3 px-4 rounded-lg flex justify-center items-center"
                    >
                      {submitting ? 'Recording...' : (
                        <><PlusCircle className="w-5 h-5 mr-2" /> Start Treatment</>
                      )}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          ) : (
            <div className="bg-gray-50 h-full rounded-xl border border-dashed border-gray-300 flex flex-col items-center justify-center p-12 text-center">
              <Syringe className="w-16 h-16 text-gray-300 mb-4" />
              <h3 className="text-xl font-medium text-gray-500">Select a case to view details or add treatment</h3>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
