import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import L from 'leaflet';
import {
  AlertTriangle,
  Clock,
  CheckCircle2,
  Users,
  Activity,
  HeartPulse,
  Flame,
  ArrowRight,
} from 'lucide-react';
import api from '../../services/api';
import type { NGOOverviewKPIs, HotspotItem, RescueCase } from '../../types';

export const NGOOverview: React.FC = () => {
  const [kpis, setKpis] = useState<NGOOverviewKPIs | null>(null);
  const [hotspots, setHotspots] = useState<HotspotItem[]>([]);
  const [cases, setCases] = useState<RescueCase[]>([]);
  const [selectedCase, setSelectedCase] = useState<RescueCase | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.Marker[]>([]);
  const navigate = useNavigate();

  const fetchOverviewData = async () => {
    try {
      const [kpiRes, hotspotRes, casesRes] = await Promise.all([
        api.get('/ngo/analytics/overview'),
        api.get('/ngo/analytics/hotspots'),
        api.get('/ngo/cases?limit=40'),
      ]);
      setKpis(kpiRes.data);
      setHotspots(hotspotRes.data || []);
      setCases(casesRes.data || []);
    } catch (err) {
      console.error('Error fetching NGO overview data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverviewData();
    const interval = setInterval(fetchOverviewData, 20000);
    return () => clearInterval(interval);
  }, []);

  // Initialize and update Live Leaflet Operations Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        zoomControl: true,
        scrollWheelZoom: false,
      }).setView([19.076, 72.8777], 12);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map);

      mapInstanceRef.current = map;
    }

    const map = mapInstanceRef.current;

    // Clear previous markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    // Add status-colored markers
    cases.forEach((c) => {
      let colorClass = 'bg-stone-500';
      if (c.triage_priority === 'CRITICAL') colorClass = 'bg-red-600 ring-4 ring-red-200 animate-bounce';
      else if (c.triage_priority === 'URGENT') colorClass = 'bg-orange-500';
      else if (c.status === 'RESPONDER_ASSIGNED') colorClass = 'bg-blue-600';
      else if (c.status === 'RESPONDER_EN_ROUTE') colorClass = 'bg-cyan-500';
      else if (c.status === 'UNDER_TREATMENT' || c.status === 'AT_VETERINARY_FACILITY') colorClass = 'bg-purple-600';
      else if (c.status === 'RECOVERING') colorClass = 'bg-emerald-500';

      const customIcon = L.divIcon({
        className: 'custom-ngo-marker',
        html: `
          <div class="relative flex items-center justify-center">
            <span class="w-7 h-7 rounded-full text-white flex items-center justify-center font-bold text-xs shadow-lg ${colorClass}">
              ${c.species ? c.species[0].toUpperCase() : 'A'}
            </span>
          </div>
        `,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });

      const marker = L.marker([c.latitude, c.longitude], { icon: customIcon }).addTo(map);

      marker.on('click', () => {
        setSelectedCase(c);
      });

      markersRef.current.push(marker);
    });

    if (cases.length > 0 && map) {
      const group = L.featureGroup(markersRef.current);
      if (group.getBounds().isValid()) {
        map.fitBounds(group.getBounds().pad(0.15));
      }
    }
  }, [cases]);

  if (loading && !kpis) {
    return (
      <div className="py-20 text-center">
        <div className="inline-block w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-stone-600 font-medium text-sm">Aggregating live operational metrics...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Operational KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-stone-200 flex flex-col justify-between">
          <span className="text-stone-500 text-xs font-bold uppercase tracking-wider flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-blue-600" /> Active Cases
          </span>
          <p className="text-2xl sm:text-3xl font-black text-stone-900 mt-2">{kpis?.active_cases ?? 0}</p>
          <span className="text-[11px] text-stone-400 mt-1">in response lifecycle</span>
        </div>

        <div className="bg-red-50/70 p-4 rounded-2xl shadow-sm border border-red-200 flex flex-col justify-between">
          <span className="text-red-700 text-xs font-bold uppercase tracking-wider flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-red-600" /> Critical Cases
          </span>
          <p className="text-2xl sm:text-3xl font-black text-red-700 mt-2">{kpis?.critical_cases ?? 0}</p>
          <span className="text-[11px] text-red-500 font-medium mt-1">immediate priority</span>
        </div>

        <div className="bg-amber-50/70 p-4 rounded-2xl shadow-sm border border-amber-200 flex flex-col justify-between">
          <span className="text-amber-800 text-xs font-bold uppercase tracking-wider flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-amber-600" /> Awaiting Responders
          </span>
          <p className="text-2xl sm:text-3xl font-black text-amber-900 mt-2">{kpis?.awaiting_responder ?? 0}</p>
          <span className="text-[11px] text-amber-600 font-medium mt-1">in auto-dispatch queue</span>
        </div>

        <div className="bg-cyan-50/70 p-4 rounded-2xl shadow-sm border border-cyan-200 flex flex-col justify-between">
          <span className="text-cyan-800 text-xs font-bold uppercase tracking-wider flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5 text-cyan-600" /> En Route
          </span>
          <p className="text-2xl sm:text-3xl font-black text-cyan-900 mt-2">{kpis?.responders_en_route ?? 0}</p>
          <span className="text-[11px] text-cyan-600 font-medium mt-1">responders mobilised</span>
        </div>

        <div className="bg-purple-50/70 p-4 rounded-2xl shadow-sm border border-purple-200 flex flex-col justify-between">
          <span className="text-purple-800 text-xs font-bold uppercase tracking-wider flex items-center gap-1.5">
            <HeartPulse className="w-3.5 h-3.5 text-purple-600" /> Under Treatment
          </span>
          <p className="text-2xl sm:text-3xl font-black text-purple-900 mt-2">{kpis?.under_treatment ?? 0}</p>
          <span className="text-[11px] text-purple-600 font-medium mt-1">at partner clinics</span>
        </div>

        <div className="bg-emerald-50/70 p-4 rounded-2xl shadow-sm border border-emerald-200 flex flex-col justify-between">
          <span className="text-emerald-800 text-xs font-bold uppercase tracking-wider flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> Recovering
          </span>
          <p className="text-2xl sm:text-3xl font-black text-emerald-900 mt-2">{kpis?.recovering ?? 0}</p>
          <span className="text-[11px] text-emerald-600 font-medium mt-1">rehabilitating</span>
        </div>
      </div>

      {/* Secondary Operational Metrics Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 bg-stone-900 text-white p-4 rounded-2xl">
        <div>
          <span className="text-[11px] text-stone-400 font-medium uppercase tracking-wider">Avg Dispatch Time</span>
          <p className="text-lg font-bold text-amber-400">{kpis?.avg_dispatch_seconds ?? 0}s</p>
        </div>
        <div>
          <span className="text-[11px] text-stone-400 font-medium uppercase tracking-wider">Avg Response Time</span>
          <p className="text-lg font-bold text-cyan-400">{kpis?.avg_response_minutes ?? 0} min</p>
        </div>
        <div>
          <span className="text-[11px] text-stone-400 font-medium uppercase tracking-wider">Case Completion Rate</span>
          <p className="text-lg font-bold text-emerald-400">{kpis?.completion_rate_pct ?? 0}%</p>
        </div>
        <div>
          <span className="text-[11px] text-stone-400 font-medium uppercase tracking-wider">Responder Availability</span>
          <p className="text-lg font-bold text-blue-400">{kpis?.responder_availability_pct ?? 0}%</p>
        </div>
      </div>

      {/* Main Grid: Live Map + Selected Case Drawer + Incident Hotspots */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live Operational Map (2 cols) */}
        <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-stone-200 overflow-hidden flex flex-col">
          <div className="p-4 border-b border-stone-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <h2 className="font-bold text-stone-900 text-sm">Live Operational Incident Map</h2>
            </div>
            <div className="flex items-center gap-2 text-xs font-semibold text-stone-500">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-600" /> Critical</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-600" /> Assigned</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-purple-600" /> Vet Care</span>
            </div>
          </div>

          <div className="relative flex-1 min-h-[420px]">
            <div ref={mapContainerRef} style={{ height: '100%', minHeight: '420px', width: '100%' }} />

            {/* Floating Quick Drawer if case selected */}
            {selectedCase && (
              <div className="absolute bottom-3 left-3 right-3 sm:right-auto sm:max-w-md bg-white/95 backdrop-blur-md p-4 rounded-xl shadow-2xl border border-stone-200 z-[1000] space-y-2">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-mono font-bold text-stone-500">{selectedCase.case_number}</span>
                    <h3 className="font-bold text-stone-900 text-sm">{selectedCase.species} Rescue</h3>
                  </div>
                  <span
                    className={`text-[10px] font-black px-2 py-0.5 rounded-full uppercase ${
                      selectedCase.triage_priority === 'CRITICAL' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-900'
                    }`}
                  >
                    {selectedCase.triage_priority}
                  </span>
                </div>
                <p className="text-xs text-stone-600 line-clamp-2">{selectedCase.triage_reason || selectedCase.description}</p>
                <div className="flex items-center justify-between pt-1 text-xs">
                  <span className="text-stone-500">Status: <strong className="text-stone-800">{selectedCase.status.replace(/_/g, ' ')}</strong></span>
                  <button
                    onClick={() => navigate(`/ngo/cases/${selectedCase.id}`)}
                    className="text-amber-600 hover:text-amber-700 font-bold flex items-center gap-1"
                  >
                    View Dossier <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Hotspots & Density Analysis (1 col) */}
        <div className="bg-white rounded-2xl shadow-sm border border-stone-200 p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-stone-100 pb-3">
            <h3 className="font-bold text-stone-900 text-sm flex items-center gap-1.5">
              <Flame className="w-4 h-4 text-orange-500" /> Incident Hotspots
            </h3>
            <span className="text-xs text-stone-400 font-medium">Spatial Cluster</span>
          </div>

          <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
            {hotspots.length === 0 ? (
              <p className="text-xs text-stone-400 py-6 text-center">No clustered hotspots identified.</p>
            ) : (
              hotspots.map((h, i) => (
                <div
                  key={i}
                  className="p-3 rounded-xl border border-stone-100 bg-stone-50/60 hover:bg-amber-50/50 transition-colors flex items-center justify-between"
                >
                  <div className="space-y-0.5 min-w-0 pr-2">
                    <p className="text-xs font-bold text-stone-900 truncate">{h.area_name}</p>
                    <p className="text-[11px] text-stone-500">Top species: {h.top_species}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="text-xs font-black text-amber-800 bg-amber-100 px-2 py-0.5 rounded-full">
                      {h.incident_count} reports
                    </span>
                    {h.critical_count > 0 && (
                      <p className="text-[10px] text-red-600 font-bold mt-0.5">{h.critical_count} critical</p>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
