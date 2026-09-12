import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  Building2, 
  Search, 
  ShieldCheck, 
  Clock, 
  AlertCircle, 
  Phone, 
  MapPin, 
  RefreshCw,
  HeartPulse,
  BedDouble,
  ExternalLink
} from 'lucide-react';
import api from '../../services/api';
import { formatApiError } from '../../utils/error';

interface VeterinaryPartner {
  id: string;
  name: string;
  address_text?: string;
  phone?: string;
  emergency_support: boolean;
  is_24_7: boolean;
  capacity?: number;
  is_verified: boolean;
  latitude: number;
  longitude: number;
  current_admitted_patients: number;
}

export const NGOVeterinary: React.FC = () => {
  const [facilities, setFacilities] = useState<VeterinaryPartner[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [filter247, setFilter247] = useState<boolean | null>(null);
  const [filterEmergency, setFilterEmergency] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchFacilities = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/ngo/veterinary');
      setFacilities(res.data || []);
    } catch (err: any) {
      console.error('Error fetching partner veterinary clinics', err);
      setError(formatApiError(err, 'Failed to load veterinary partner network'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFacilities();
  }, []);

  const filteredFacilities = facilities.filter((f) => {
    if (search) {
      const query = search.toLowerCase();
      const matchName = f.name?.toLowerCase().includes(query);
      const matchAddr = f.address_text?.toLowerCase().includes(query);
      if (!matchName && !matchAddr) return false;
    }
    if (filter247 !== null && f.is_24_7 !== filter247) return false;
    if (filterEmergency !== null && f.emergency_support !== filterEmergency) return false;
    return true;
  });

  const totalFacilities = facilities.length;
  const emergencyReady = facilities.filter((f) => f.emergency_support).length;
  const roundTheClock = facilities.filter((f) => f.is_24_7).length;
  const totalAdmitted = facilities.reduce((acc, f) => acc + (f.current_admitted_patients || 0), 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-stone-900 tracking-tight flex items-center gap-2.5">
            <Building2 className="w-7 h-7 text-emerald-600" />
            Partner Veterinary Network
          </h1>
          <p className="text-sm text-stone-600 mt-1">
            Authorized clinics, 24/7 trauma centers, and live patient intake across your jurisdiction.
          </p>
        </div>
        <button
          onClick={fetchFacilities}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl bg-white border border-stone-200 text-stone-700 hover:bg-stone-50 hover:border-stone-300 transition shadow-sm"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Clinics
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm flex items-center gap-2">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Network KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-2xl border border-stone-200/80 shadow-sm">
          <div className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Partner Clinics</div>
          <div className="text-2xl font-black text-stone-900 mt-1">{totalFacilities}</div>
          <div className="text-xs text-stone-500 mt-1">Network facilities</div>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-stone-200/80 shadow-sm">
          <div className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Emergency Trauma</div>
          <div className="text-2xl font-black text-red-600 mt-1">{emergencyReady}</div>
          <div className="text-xs text-stone-500 mt-1">Surgical / critical ready</div>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-stone-200/80 shadow-sm">
          <div className="text-xs font-semibold text-stone-500 uppercase tracking-wider">24/7 Round the Clock</div>
          <div className="text-2xl font-black text-indigo-600 mt-1">{roundTheClock}</div>
          <div className="text-xs text-stone-500 mt-1">Always open</div>
        </div>
        <div className="bg-white p-4 rounded-2xl border border-stone-200/80 shadow-sm">
          <div className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Admitted Patients</div>
          <div className="text-2xl font-black text-purple-600 mt-1">{totalAdmitted}</div>
          <div className="text-xs text-stone-500 mt-1">Active animal recoveries</div>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="bg-white p-4 rounded-2xl border border-stone-200/80 shadow-sm flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400" />
          <input
            type="text"
            placeholder="Search clinics by name, area, or street..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm bg-stone-50 border border-stone-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          <button
            onClick={() => setFilterEmergency((prev) => (prev === true ? null : true))}
            className={`px-3 py-1.5 text-xs font-bold rounded-xl border transition ${
              filterEmergency === true
                ? 'bg-red-50 border-red-300 text-red-700'
                : 'bg-stone-50 border-stone-200 text-stone-600 hover:bg-stone-100'
            }`}
          >
            Emergency Trauma
          </button>
          <button
            onClick={() => setFilter247((prev) => (prev === true ? null : true))}
            className={`px-3 py-1.5 text-xs font-bold rounded-xl border transition ${
              filter247 === true
                ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                : 'bg-stone-50 border-stone-200 text-stone-600 hover:bg-stone-100'
            }`}
          >
            24/7 Service
          </button>
          {(filterEmergency !== null || filter247 !== null || search) && (
            <button
              onClick={() => {
                setFilterEmergency(null);
                setFilter247(null);
                setSearch('');
              }}
              className="text-xs text-stone-500 underline hover:text-stone-800 ml-1"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Facilities Cards Grid */}
      {loading ? (
        <div className="bg-white rounded-2xl border border-stone-200/80 p-12 text-center text-stone-500 shadow-sm">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-emerald-600 mb-3" />
          <p className="text-sm font-medium">Loading partner network...</p>
        </div>
      ) : filteredFacilities.length === 0 ? (
        <div className="bg-white rounded-2xl border border-stone-200/80 p-12 text-center text-stone-500 shadow-sm">
          <Building2 className="w-10 h-10 mx-auto text-stone-300 mb-2" />
          <p className="text-base font-bold text-stone-800">No partner clinics match your filters</p>
          <p className="text-xs text-stone-500 mt-1">Try clearing filters or adding clinic partners.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredFacilities.map((f) => {
            const capacity = f.capacity || 20;
            const admitted = f.current_admitted_patients || 0;
            const occupancyPct = Math.min(100, Math.round((admitted / capacity) * 100));

            return (
              <div
                key={f.id}
                className="bg-white rounded-2xl border border-stone-200/80 shadow-sm hover:shadow-md transition-shadow p-5 flex flex-col justify-between"
              >
                <div>
                  {/* Top Badges */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {f.is_verified && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <ShieldCheck className="w-3 h-3" /> Verified
                        </span>
                      )}
                      {f.is_24_7 && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                          <Clock className="w-3 h-3" /> 24/7
                        </span>
                      )}
                      {f.emergency_support && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold rounded-full bg-red-50 text-red-700 border border-red-200">
                          <HeartPulse className="w-3 h-3" /> Trauma
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Title & Info */}
                  <h2 className="text-base font-bold text-stone-900 mt-3">{f.name}</h2>
                  
                  {f.address_text && (
                    <div className="flex items-start gap-1.5 text-xs text-stone-600 mt-2">
                      <MapPin className="w-3.5 h-3.5 flex-shrink-0 text-stone-400 mt-0.5" />
                      <span>{f.address_text}</span>
                    </div>
                  )}

                  {f.phone && (
                    <div className="flex items-center gap-1.5 text-xs text-stone-600 mt-1.5">
                      <Phone className="w-3.5 h-3.5 flex-shrink-0 text-stone-400" />
                      <a href={`tel:${f.phone}`} className="hover:underline hover:text-emerald-700">
                        {f.phone}
                      </a>
                    </div>
                  )}

                  {/* Patient Intake Bar */}
                  <div className="mt-4 pt-3 border-t border-stone-100">
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="text-stone-500 font-medium flex items-center gap-1">
                        <BedDouble className="w-3.5 h-3.5 text-stone-400" /> Patient Intake
                      </span>
                      <span className="font-bold text-stone-800">
                        {admitted} / {capacity} beds
                      </span>
                    </div>
                    <div className="w-full bg-stone-100 rounded-full h-2 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          occupancyPct >= 90
                            ? 'bg-red-500'
                            : occupancyPct >= 70
                            ? 'bg-amber-500'
                            : 'bg-emerald-500'
                        }`}
                        style={{ width: `${occupancyPct}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Footer Action */}
                <div className="mt-5 pt-3 border-t border-stone-100 flex items-center justify-between">
                  <span className="text-xs text-stone-400 font-medium">
                    {occupancyPct}% Capacity
                  </span>
                  <Link
                    to={`/ngo/cases`}
                    className="inline-flex items-center gap-1 text-xs font-bold text-emerald-700 hover:text-emerald-800 hover:underline"
                  >
                    View Cases <ExternalLink className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
