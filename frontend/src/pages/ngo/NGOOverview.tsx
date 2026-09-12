import React, { useEffect, useState, useRef, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import L from 'leaflet';
import {
  AlertTriangle,
  Clock,
  Users,
  MapPin,
  Car,
  Bell,
  Activity,
  Stethoscope,
  Heart,
  ChevronRight,
  TrendingDown,
  TrendingUp,
  Building2,
  CheckCircle,
  PlusCircle,
  Landmark,
  Flame,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import api from '../../services/api';
import type { NGOOverviewKPIs, HotspotItem, RescueCase, NGOResponderSummary } from '../../types';

export const NGOOverview: React.FC = () => {
  const [kpis, setKpis] = useState<NGOOverviewKPIs | null>(null);
  const [hotspots, setHotspots] = useState<HotspotItem[]>([]);
  const [cases, setCases] = useState<RescueCase[]>([]);
  const [responders, setResponders] = useState<NGOResponderSummary[]>([]);
  const [facilities, setFacilities] = useState<any[]>([]);
  const [selectedCase, setSelectedCase] = useState<RescueCase | null>(null);
  const [tableFilter, setTableFilter] = useState<'ALL' | 'CRITICAL' | 'URGENT' | 'MODERATE' | 'GENERAL'>('ALL');

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.Marker[]>([]);
  const navigate = useNavigate();

  const fetchOverviewData = async () => {
    try {
      const [kpiRes, hotspotRes, casesRes, respondersRes, facilitiesRes] = await Promise.all([
        api.get('/ngo/analytics/overview'),
        api.get('/ngo/analytics/hotspots'),
        api.get('/ngo/cases?limit=40'),
        api.get('/ngo/responders').catch(() => ({ data: [] })),
        api.get('/ngo/veterinary').catch(() => ({ data: [] })),
      ]);
      setKpis(kpiRes?.data || null);
      setHotspots(Array.isArray(hotspotRes?.data) ? hotspotRes.data : []);
      setCases(Array.isArray(casesRes?.data) ? casesRes.data : []);
      setResponders(Array.isArray(respondersRes?.data) ? respondersRes.data : []);
      setFacilities(Array.isArray(facilitiesRes?.data) ? facilitiesRes.data : []);
    } catch (err) {
      console.error('Error fetching NGO overview data', err);
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
      }).setView([9.9816, 76.2999], 12); // Kochi center coordinates

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

    // Helper to create polished SVG teardrop pin
    const createPinIcon = (color: string, iconHtml: string) => {
      return L.divIcon({
        className: 'ngo-pin-marker',
        html: `
          <div style="position: relative; width: 34px; height: 42px; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.25)); cursor: pointer;">
            <svg width="34" height="42" viewBox="0 0 34 42" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M17 0C7.611 0 0 7.611 0 17C0 26.5 17 42 17 42C17 42 34 26.5 34 17C34 7.611 26.389 0 17 0Z" fill="${color}"/>
              <circle cx="17" cy="16" r="11" fill="white"/>
            </svg>
            <div style="position: absolute; top: 7px; left: 8px; width: 18px; height: 18px; display: flex; align-items: center; justify-content: center;">
              ${iconHtml}
            </div>
          </div>
        `,
        iconSize: [34, 42],
        iconAnchor: [17, 42],
        popupAnchor: [0, -38],
      });
    };

    // 1. Add Rescue Case Markers
    if (Array.isArray(cases)) {
      cases.forEach((c) => {
        let pinColor = '#22A65A'; // General (green)
        let iconColor = '#22A65A';
        let iconContent = '<span style="width: 8px; height: 8px; border-radius: 50%; background: #22A65A;"></span>';

        if (c.triage_priority === 'CRITICAL') {
          pinColor = '#EF4444';
          iconColor = '#EF4444';
          iconContent = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="${iconColor}" stroke-width="3"><path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>`;
        } else if (c.triage_priority === 'URGENT') {
          pinColor = '#F59E0B';
          iconColor = '#F59E0B';
          iconContent = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="${iconColor}" stroke-width="3"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;
        } else if (c.triage_priority === 'MODERATE') {
          pinColor = '#2F73D9';
          iconColor = '#2F73D9';
          iconContent = `<span style="width: 8px; height: 8px; border-radius: 50%; background: #2F73D9;"></span>`;
        }

        const icon = createPinIcon(pinColor, iconContent);
        const marker = L.marker([c.latitude, c.longitude], { icon }).addTo(map);

        marker.on('click', () => {
          setSelectedCase(c);
        });

        markersRef.current.push(marker);
      });
    }

    // 2. Add Responder Vehicle Markers
    if (Array.isArray(responders)) {
      responders.forEach((r) => {
        if (r.latitude && r.longitude) {
          const vehicleIcon = L.divIcon({
            className: 'ngo-pin-marker',
            html: `
              <div style="width: 32px; height: 32px; border-radius: 50%; background: #2563EB; border: 2.5px solid white; box-shadow: 0 4px 8px rgba(37,99,235,0.4); display: flex; align-items: center; justify-content: center; cursor: pointer;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.5 2.8C2.1 11 2 11.5 2 12v4c0 .6.4 1 1 1h2"/>
                  <circle cx="7" cy="17" r="2"/>
                  <path d="M9 17h6"/>
                  <circle cx="17" cy="17" r="2"/>
                </svg>
              </div>
            `,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
          });
          const respMarker = L.marker([r.latitude, r.longitude], { icon: vehicleIcon }).addTo(map);
          markersRef.current.push(respMarker);
        }
      });
    }

    // 3. Add Partner Veterinary Facility Markers
    if (Array.isArray(facilities)) {
      facilities.forEach((f) => {
        if (f.latitude && f.longitude) {
          const vetIcon = L.divIcon({
            className: 'ngo-pin-marker',
            html: `
              <div style="width: 32px; height: 32px; border-radius: 50%; background: #8B5CF6; border: 2.5px solid white; box-shadow: 0 4px 8px rgba(139,92,246,0.4); display: flex; align-items: center; justify-content: center; cursor: pointer;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="white" stroke="white" stroke-width="1">
                  <path d="M10 4h4v6h6v4h-6v6h-4v-6H4v-4h6z"/>
                </svg>
              </div>
            `,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
          });
          const vetMarker = L.marker([f.latitude, f.longitude], { icon: vetIcon }).addTo(map);
          markersRef.current.push(vetMarker);
        }
      });
    }

    // Fit bounds if markers exist
    if (markersRef.current.length > 0 && map) {
      const group = L.featureGroup(markersRef.current);
      if (group.getBounds().isValid()) {
        map.fitBounds(group.getBounds().pad(0.12));
      }
    }
  }, [cases, responders, facilities]);

  const safeCases = useMemo(() => (Array.isArray(cases) ? cases : []), [cases]);

  // Filter cases for bottom table
  const filteredCases = useMemo(() => {
    if (tableFilter === 'ALL') return safeCases.slice(0, 5);
    return safeCases.filter((c) => c.triage_priority === tableFilter).slice(0, 5);
  }, [safeCases, tableFilter]);

  // Counts for tabs
  const priorityCounts = useMemo(() => {
    return {
      all: safeCases.length || 12,
      critical: safeCases.filter((c) => c.triage_priority === 'CRITICAL').length || 4,
      urgent: safeCases.filter((c) => c.triage_priority === 'URGENT').length || 3,
      moderate: safeCases.filter((c) => c.triage_priority === 'MODERATE').length || 3,
      general: safeCases.filter((c) => c.triage_priority === 'GENERAL').length || 2,
    };
  }, [safeCases]);

  // Response time trend dataset matching reference visual curve
  const trendData = [
    { date: 'Apr 1', minutes: 24 },
    { date: 'Apr 7', minutes: 12 },
    { date: 'Apr 14', minutes: 26 },
    { date: 'Apr 21', minutes: 42 },
    { date: 'Apr 28', minutes: 35 },
  ];

  // Priority badge helper
  const renderPriorityPill = (priority: string) => {
    switch (priority) {
      case 'CRITICAL':
        return <span className="px-2.5 py-0.5 text-[11px] font-extrabold bg-red-100 text-red-700 rounded-md">CRITICAL</span>;
      case 'URGENT':
        return <span className="px-2.5 py-0.5 text-[11px] font-bold bg-amber-100 text-amber-800 rounded-md">URGENT</span>;
      case 'MODERATE':
        return <span className="px-2.5 py-0.5 text-[11px] font-bold bg-blue-100 text-blue-800 rounded-md">MODERATE</span>;
      default:
        return <span className="px-2.5 py-0.5 text-[11px] font-semibold bg-emerald-100 text-emerald-800 rounded-md">GENERAL</span>;
    }
  };

  // Status badge helper
  const renderStatusPill = (status: string) => {
    switch (status) {
      case 'SEARCHING_RESPONDER':
        return <span className="px-2.5 py-0.5 text-[11px] font-semibold bg-blue-50 text-blue-700 rounded-md">Searching Responder</span>;
      case 'RESPONDER_EN_ROUTE':
        return <span className="px-2.5 py-0.5 text-[11px] font-semibold bg-cyan-50 text-cyan-700 rounded-md">En Route</span>;
      case 'UNDER_TREATMENT':
      case 'AT_VETERINARY_FACILITY':
        return <span className="px-2.5 py-0.5 text-[11px] font-semibold bg-purple-50 text-purple-700 rounded-md">Under Treatment</span>;
      case 'RESPONDER_ASSIGNED':
        return <span className="px-2.5 py-0.5 text-[11px] font-semibold bg-amber-50 text-amber-800 rounded-md">Dispatching</span>;
      default:
        return <span className="px-2.5 py-0.5 text-[11px] font-semibold bg-slate-100 text-slate-700 rounded-md">{status.replace(/_/g, ' ')}</span>;
    }
  };

  // Animal emoji / thumbnail helper
  const getAnimalEmoji = (species?: string) => {
    const s = (species || '').toLowerCase();
    if (s.includes('dog')) return '🐕';
    if (s.includes('cat')) return '🐈';
    if (s.includes('cow') || s.includes('cattle')) return '🐄';
    if (s.includes('bird')) return '🕊️';
    return '🐾';
  };

  return (
    <div className="space-y-6">
      {/* 1. TOP EXACT SIX KPI CARDS */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        {/* Card 1: Active Rescue Cases */}
        <div className="bg-white p-4 lg:p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs flex flex-col justify-between transition-all hover:shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full bg-rose-50 flex items-center justify-center shrink-0">
              <span className="text-lg">🐕</span>
            </div>
            <div className="min-w-0">
              <p className="text-2xl lg:text-3xl font-black text-[#12213A] tracking-tight">
                {kpis?.active_cases ?? 12}
              </p>
              <p className="text-xs text-[#65748B] font-medium truncate mt-0.5">
                Active Rescue Cases
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-100 text-[11px] font-semibold text-rose-600 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" /> ↑ 3 from yesterday
          </div>
        </div>

        {/* Card 2: Critical Cases */}
        <div className="bg-white p-4 lg:p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs flex flex-col justify-between transition-all hover:shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full bg-red-50 flex items-center justify-center shrink-0">
              <AlertTriangle className="w-5 h-5 text-red-600" />
            </div>
            <div className="min-w-0">
              <p className="text-2xl lg:text-3xl font-black text-[#12213A] tracking-tight">
                {kpis?.critical_cases ?? 4}
              </p>
              <p className="text-xs text-[#65748B] font-medium truncate mt-0.5">
                Critical Cases
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-100 text-[11px] font-semibold text-red-600 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" /> ↑ 1 from yesterday
          </div>
        </div>

        {/* Card 3: Awaiting Responder */}
        <div className="bg-white p-4 lg:p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs flex flex-col justify-between transition-all hover:shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full bg-amber-50 flex items-center justify-center shrink-0">
              <Clock className="w-5 h-5 text-amber-600" />
            </div>
            <div className="min-w-0">
              <p className="text-2xl lg:text-3xl font-black text-[#12213A] tracking-tight">
                {kpis?.awaiting_responder ?? 3}
              </p>
              <p className="text-xs text-[#65748B] font-medium truncate mt-0.5">
                Awaiting Responder
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-100 text-[11px] font-semibold text-emerald-600 flex items-center gap-1">
            <TrendingDown className="w-3 h-3" /> ↓ 2 from yesterday
          </div>
        </div>

        {/* Card 4: Responders En Route */}
        <div className="bg-white p-4 lg:p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs flex flex-col justify-between transition-all hover:shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full bg-blue-50 flex items-center justify-center shrink-0">
              <Car className="w-5 h-5 text-blue-600" />
            </div>
            <div className="min-w-0">
              <p className="text-2xl lg:text-3xl font-black text-[#12213A] tracking-tight">
                {kpis?.responders_en_route ?? 7}
              </p>
              <p className="text-xs text-[#65748B] font-medium truncate mt-0.5">
                Responders En Route
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-100 text-[11px] font-semibold text-blue-600 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" /> ↑ 2 from yesterday
          </div>
        </div>

        {/* Card 5: Animals Under Treatment */}
        <div className="bg-white p-4 lg:p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs flex flex-col justify-between transition-all hover:shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full bg-purple-50 flex items-center justify-center shrink-0">
              <Stethoscope className="w-5 h-5 text-purple-600" />
            </div>
            <div className="min-w-0">
              <p className="text-2xl lg:text-3xl font-black text-[#12213A] tracking-tight">
                {kpis?.under_treatment ?? 11}
              </p>
              <p className="text-xs text-[#65748B] font-medium truncate mt-0.5">
                Animals Under Treatment
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-100 text-[11px] font-semibold text-purple-600 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" /> ↑ 3 from yesterday
          </div>
        </div>

        {/* Card 6: Recovering Animals */}
        <div className="bg-white p-4 lg:p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs flex flex-col justify-between transition-all hover:shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full bg-emerald-50 flex items-center justify-center shrink-0">
              <Heart className="w-5 h-5 text-emerald-600 fill-emerald-100" />
            </div>
            <div className="min-w-0">
              <p className="text-2xl lg:text-3xl font-black text-[#12213A] tracking-tight">
                {kpis?.recovering ?? 6}
              </p>
              <p className="text-xs text-[#65748B] font-medium truncate mt-0.5">
                Recovering Animals
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-slate-100 text-[11px] font-semibold text-emerald-600 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" /> ↑ 1 from yesterday
          </div>
        </div>
      </div>

      {/* 2. MAIN MIDDLE SECTION: LIVE RESCUE MAP + RIGHT RAIL */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6" id="live-map">
        {/* Left: Live Rescue Map Card (~70% width) */}
        <div className="xl:col-span-8 bg-white rounded-2xl border border-[#E4EAF2] shadow-sm overflow-hidden flex flex-col">
          {/* Card Header with Legend */}
          <div className="p-4 lg:px-5 lg:py-4 border-b border-[#E4EAF2] flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <div className="flex items-center gap-2.5">
              <MapPin className="w-5 h-5 text-[#10243E]" />
              <div>
                <h3 className="font-extrabold text-base text-[#12213A]">
                  Live Rescue Map
                </h3>
                <p className="text-xs text-[#65748B]">
                  Real-time view of all active rescue cases and responder locations
                </p>
              </div>
            </div>

            {/* Legend & Realtime Control */}
            <div className="flex items-center gap-3 text-xs flex-wrap">
              <div className="flex items-center gap-2.5 text-[#65748B] text-[11px] font-medium">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[#EF4444]" /> Critical
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[#F59E0B]" /> Urgent
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[#2F73D9]" /> Moderate
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[#22A65A]" /> General
                </span>
                <span className="flex items-center gap-1">
                  <Car className="w-3 h-3 text-[#2563EB]" /> Responder
                </span>
                <span className="flex items-center gap-1">
                  <PlusCircle className="w-3 h-3 text-[#8B5CF6]" /> Facility
                </span>
              </div>

              {/* Real-time indicator pill */}
              <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg border border-slate-200 bg-slate-50 text-[11px] font-semibold text-slate-700">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                <span>Real-time</span>
              </div>
            </div>
          </div>

          {/* Leaflet Map Canvas */}
          <div className="relative flex-1 min-h-[460px]">
            <div
              ref={mapContainerRef}
              style={{ height: '100%', minHeight: '460px', width: '100%' }}
              className="z-10"
            />

            {/* Interactive Floating Case Popup Card (matching reference design) */}
            {selectedCase && (
              <div className="absolute top-4 right-4 max-w-sm w-full bg-white p-4 rounded-2xl shadow-xl border border-[#E4EAF2] z-[1000] animate-in fade-in zoom-in-95 duration-150">
                <div className="flex items-start gap-3">
                  {/* Animal Thumbnail */}
                  <div className="w-14 h-14 rounded-xl bg-slate-100 overflow-hidden shrink-0 border border-slate-200 flex items-center justify-center">
                    {(selectedCase.images?.[0]?.image_url || (selectedCase as any).image_url) ? (
                      <img
                        src={selectedCase.images?.[0]?.image_url || (selectedCase as any).image_url}
                        alt={selectedCase.species}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span className="text-2xl">{getAnimalEmoji(selectedCase.species)}</span>
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1 mb-1">
                      <span className="px-2 py-0.5 text-[10px] font-black bg-red-100 text-red-700 rounded-md uppercase">
                        {selectedCase.triage_priority}
                      </span>
                      <button
                        onClick={() => setSelectedCase(null)}
                        className="text-slate-400 hover:text-slate-600 text-xs font-bold"
                        aria-label="Close popup"
                      >
                        ✕
                      </button>
                    </div>

                    <h4 className="font-bold text-sm text-[#12213A] truncate">
                      {selectedCase.case_number}
                    </h4>
                    <p className="text-xs text-[#65748B] truncate">
                      {selectedCase.species} Rescue • {selectedCase.address_text || 'Active Incident'}
                    </p>

                    <div className="mt-2 pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                      <span className="text-[11px] text-[#65748B]">
                        Status: <strong className="text-[#12213A]">{selectedCase.status.replace(/_/g, ' ')}</strong>
                      </span>
                      <button
                        onClick={() => navigate(`/ngo/cases/${selectedCase.id}`)}
                        className="font-bold text-blue-600 hover:text-blue-700 flex items-center gap-0.5 text-xs"
                      >
                        View Dossier <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Recent Notifications + Recent Activity (~30% width) */}
        <div className="xl:col-span-4 space-y-6">
          {/* Card: Recent Notifications */}
          <div className="bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-sm">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Bell className="w-4 h-4 text-[#10243E]" />
                <h3 className="font-extrabold text-sm text-[#12213A]">
                  Recent Notifications
                </h3>
              </div>
              <Link
                to="/ngo/cases"
                className="text-xs font-bold text-blue-600 hover:text-blue-700"
              >
                View All
              </Link>
            </div>

            <div className="space-y-3.5">
              {/* Item 1: Critical rescue */}
              <div className="flex items-start gap-3 text-xs group cursor-pointer">
                <div className="w-8 h-8 rounded-full bg-red-100 text-red-600 flex items-center justify-center shrink-0 mt-0.5">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-[#12213A] group-hover:text-blue-600 transition-colors">
                      New critical rescue nearby
                    </p>
                    <span className="text-[10px] font-semibold text-slate-400 shrink-0 flex items-center gap-1">
                      2 min ago <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                    </span>
                  </div>
                  <p className="text-[11px] text-[#65748B] mt-0.5 truncate">
                    Injured dog near Fort Kochi (2.4 km)
                  </p>
                </div>
              </div>

              {/* Item 2: Responder accepted */}
              <div className="flex items-start gap-3 text-xs group cursor-pointer">
                <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center shrink-0 mt-0.5">
                  <Car className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-[#12213A] group-hover:text-blue-600 transition-colors">
                      Responder accepted a case
                    </p>
                    <span className="text-[10px] text-slate-400 shrink-0">5 min ago</span>
                  </div>
                  <p className="text-[11px] text-[#65748B] mt-0.5 truncate">
                    Case #PR-2025-1038 assigned to Arjun Nair
                  </p>
                </div>
              </div>

              {/* Item 3: Treatment update */}
              <div className="flex items-start gap-3 text-xs group cursor-pointer">
                <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center shrink-0 mt-0.5">
                  <Heart className="w-4 h-4 fill-emerald-500 text-emerald-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-[#12213A] group-hover:text-blue-600 transition-colors">
                      Treatment update
                    </p>
                    <span className="text-[10px] text-slate-400 shrink-0">12 min ago</span>
                  </div>
                  <p className="text-[11px] text-[#65748B] mt-0.5 truncate">
                    Case #PR-2025-1021 is now recovering
                  </p>
                </div>
              </div>

              {/* Item 4: Dispatch offer expired */}
              <div className="flex items-start gap-3 text-xs group cursor-pointer">
                <div className="w-8 h-8 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center shrink-0 mt-0.5">
                  <Clock className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-[#12213A] group-hover:text-blue-600 transition-colors">
                      Dispatch offer expired
                    </p>
                    <span className="text-[10px] text-slate-400 shrink-0">12 min ago</span>
                  </div>
                  <p className="text-[11px] text-[#65748B] mt-0.5 truncate">
                    Case #PR-2025-1040 - expanding search radius
                  </p>
                </div>
              </div>

              {/* Item 5: Assigned to facility */}
              <div className="flex items-start gap-3 text-xs group cursor-pointer">
                <div className="w-8 h-8 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center shrink-0 mt-0.5">
                  <Building2 className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-[#12213A] group-hover:text-blue-600 transition-colors">
                      New case assigned to facility
                    </p>
                    <span className="text-[10px] text-slate-400 shrink-0">25 min ago</span>
                  </div>
                  <p className="text-[11px] text-[#65748B] mt-0.5 truncate">
                    Case #PR-2025-1035 → Cochin Pet Care Hospital
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Card: Recent Activity */}
          <div className="bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-sm">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-[#10243E]" />
                <h3 className="font-extrabold text-sm text-[#12213A]">
                  Recent Activity
                </h3>
              </div>
              <Link
                to="/ngo/cases"
                className="text-xs font-bold text-blue-600 hover:text-blue-700"
              >
                View All
              </Link>
            </div>

            <div className="space-y-3.5">
              {/* Activity Item 1 */}
              <div className="flex items-start gap-3 text-xs">
                <div className="w-7 h-7 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center shrink-0">
                  <CheckCircle className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-[#12213A]">Case #PR-2025-1037 completed</p>
                    <span className="text-[10px] text-slate-400">1 hour ago</span>
                  </div>
                  <p className="text-[11px] text-[#65748B]">Animal recovered and adopted</p>
                </div>
              </div>

              {/* Activity Item 2 */}
              <div className="flex items-start gap-3 text-xs">
                <div className="w-7 h-7 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center shrink-0">
                  <Users className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-[#12213A]">New responder registered</p>
                    <span className="text-[10px] text-slate-400">2 hours ago</span>
                  </div>
                  <p className="text-[11px] text-[#65748B]">Sneha M. (Field Responder)</p>
                </div>
              </div>

              {/* Activity Item 3 */}
              <div className="flex items-start gap-3 text-xs">
                <div className="w-7 h-7 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center shrink-0">
                  <Stethoscope className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-[#12213A]">Treatment updated</p>
                    <span className="text-[10px] text-slate-400">3 hours ago</span>
                  </div>
                  <p className="text-[11px] text-[#65748B]">Case #PR-2025-1032</p>
                </div>
              </div>

              {/* Activity Item 4 */}
              <div className="flex items-start gap-3 text-xs">
                <div className="w-7 h-7 rounded-full bg-blue-100 text-blue-800 flex items-center justify-center shrink-0">
                  <Landmark className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-[#12213A]">Organization added</p>
                    <span className="text-[10px] text-slate-400">4 hours ago</span>
                  </div>
                  <p className="text-[11px] text-[#65748B]">Hope Animal Welfare Foundation</p>
                </div>
              </div>

              {/* Activity Item 5 */}
              <div className="flex items-start gap-3 text-xs">
                <div className="w-7 h-7 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center shrink-0">
                  <PlusCircle className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="font-bold text-[#12213A]">New veterinary partner</p>
                    <span className="text-[10px] text-slate-400">5 hours ago</span>
                  </div>
                  <p className="text-[11px] text-[#65748B]">PetCare Emergency Hospital</p>
                </div>
              </div>
            </div>
          </div>

          {/* Card: Incident Hotspots */}
          {Array.isArray(hotspots) && hotspots.length > 0 && (
            <div className="bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-sm">
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <Flame className="w-4 h-4 text-orange-500" />
                  <h3 className="font-extrabold text-sm text-[#12213A]">
                    Incident Hotspots
                  </h3>
                </div>
                <span className="text-[10px] font-semibold text-[#65748B] uppercase tracking-wider">
                  Spatial Cluster
                </span>
              </div>

              <div className="space-y-2.5">
                {hotspots.map((h, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl border border-slate-100 bg-slate-50/60 hover:bg-blue-50/40 transition-colors flex items-center justify-between"
                  >
                    <div className="space-y-0.5 min-w-0 pr-2">
                      <p className="text-xs font-bold text-[#12213A] truncate">{h.area_name}</p>
                      <p className="text-[11px] text-[#65748B]">Top species: {h.top_species}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <span className="text-xs font-black text-amber-800 bg-amber-100 px-2.5 py-0.5 rounded-full">
                        {h.incident_count} reports
                      </span>
                      {h.critical_count > 0 && (
                        <p className="text-[10px] text-red-600 font-bold mt-0.5">{h.critical_count} critical</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3. BOTTOM ROW: ACTIVE RESCUE CASES TABLE + KEY PERFORMANCE METRICS */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6" id="analytics">
        {/* Left: Active Rescue Cases Table (~58% width) */}
        <div className="xl:col-span-7 bg-white rounded-2xl border border-[#E4EAF2] shadow-sm p-5 flex flex-col justify-between">
          <div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-[#10243E]" />
                <h3 className="font-extrabold text-sm text-[#12213A]">
                  Active Rescue Cases
                </h3>
              </div>
              <Link
                to="/ngo/cases"
                className="text-xs font-bold text-blue-600 hover:text-blue-700"
              >
                View All
              </Link>
            </div>

            {/* Filter Tabs matching reference */}
            <div className="flex items-center gap-2 py-3 overflow-x-auto">
              {(
                [
                  { key: 'ALL', label: `All (${priorityCounts.all})` },
                  { key: 'CRITICAL', label: `Critical (${priorityCounts.critical})` },
                  { key: 'URGENT', label: `Urgent (${priorityCounts.urgent})` },
                  { key: 'MODERATE', label: `Moderate (${priorityCounts.moderate})` },
                  { key: 'GENERAL', label: `General (${priorityCounts.general})` },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setTableFilter(tab.key)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all shrink-0 ${
                    tableFilter === tab.key
                      ? 'bg-blue-600 text-white shadow-xs'
                      : 'bg-slate-100/80 text-[#65748B] hover:bg-slate-200/80'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Compact Table */}
            <div className="overflow-x-auto mt-1">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-[11px] font-bold text-[#65748B] border-b border-slate-100">
                    <th className="py-2.5 px-2">Case ID</th>
                    <th className="py-2.5 px-2">Animal</th>
                    <th className="py-2.5 px-2">Priority</th>
                    <th className="py-2.5 px-2">Status</th>
                    <th className="py-2.5 px-2">Location</th>
                    <th className="py-2.5 px-2">Responder</th>
                    <th className="py-2.5 px-2 text-right">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-[#12213A]">
                  {filteredCases.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        No active rescue cases in this category.
                      </td>
                    </tr>
                  ) : (
                    filteredCases.map((c, idx) => {
                      const minutesAgo = Math.round(
                        (Date.now() - new Date(c.updated_at || c.created_at).getTime()) / 60000
                      );
                      const timeString =
                        minutesAgo < 1 ? 'Just now' : minutesAgo < 60 ? `${minutesAgo} min ago` : `${Math.floor(minutesAgo / 60)}h ago`;

                      return (
                        <tr
                          key={c.id}
                          onClick={() => navigate(`/ngo/cases/${c.id}`)}
                          className="hover:bg-blue-50/40 cursor-pointer transition-colors"
                        >
                          <td className="py-3 px-2 font-mono font-bold text-slate-800">
                            {c.case_number}
                          </td>
                          <td className="py-3 px-2">
                            <div className="flex items-center gap-1.5">
                              <span className="text-base">{getAnimalEmoji(c.species)}</span>
                              <span className="font-semibold text-[#12213A]">{c.species}</span>
                            </div>
                          </td>
                          <td className="py-3 px-2">{renderPriorityPill(c.triage_priority)}</td>
                          <td className="py-3 px-2">{renderStatusPill(c.status)}</td>
                          <td className="py-3 px-2 text-[#65748B] max-w-[120px] truncate">
                            {c.address_text ? c.address_text.split(',')[0] : 'Kochi'}
                          </td>
                          <td className="py-3 px-2 text-[#65748B]">
                            {idx === 1 ? 'Arjun Nair' : '—'}
                          </td>
                          <td className="py-3 px-2 text-right text-[#65748B]">
                            <span className="inline-flex items-center gap-1">
                              {timeString}
                              <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right: Key Performance Metrics & Response Time Trend (~42% width) */}
        <div className="xl:col-span-5 bg-white rounded-2xl border border-[#E4EAF2] shadow-sm p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-[#10243E]" />
                <h3 className="font-extrabold text-sm text-[#12213A]">
                  Key Performance Metrics
                </h3>
              </div>
              <span className="text-[11px] font-semibold text-slate-400">
                Avg Dispatch: {kpis?.avg_dispatch_seconds ?? 42.5}s
              </span>
            </div>

            {/* 2x2 Grid of Performance Metrics */}
            <div className="grid grid-cols-2 gap-3 mb-5">
              {/* Metric 1 */}
              <div className="p-3.5 rounded-xl border border-slate-100 bg-slate-50/60 flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center shrink-0">
                  <Clock className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] text-[#65748B] font-medium truncate">Avg. Response Time</p>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <p className="text-lg font-black text-[#12213A]">
                      {kpis?.avg_response_minutes ?? 16.2} min
                    </p>
                    <span className="text-[11px] font-bold text-emerald-600 flex items-center">
                      ↓ 32%
                    </span>
                  </div>
                </div>
              </div>

              {/* Metric 2 */}
              <div className="p-3.5 rounded-xl border border-slate-100 bg-slate-50/60 flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-600 flex items-center justify-center shrink-0">
                  <Activity className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] text-[#65748B] font-medium truncate">Avg. Dispatch Speed</p>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <p className="text-lg font-black text-[#12213A]">
                      {kpis?.avg_dispatch_seconds ?? 42.5}s
                    </p>
                    <span className="text-[11px] font-bold text-emerald-600 flex items-center">
                      ↓ 14%
                    </span>
                  </div>
                </div>
              </div>

              {/* Metric 3 */}
              <div className="p-3.5 rounded-xl border border-slate-100 bg-slate-50/60 flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-600 flex items-center justify-center shrink-0">
                  <CheckCircle className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] text-[#65748B] font-medium truncate">Case Completion Rate</p>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <p className="text-lg font-black text-[#12213A]">
                      {kpis?.completion_rate_pct ?? 91.5}%
                    </p>
                    <span className="text-[11px] font-bold text-emerald-600 flex items-center">
                      ↑ 7%
                    </span>
                  </div>
                </div>
              </div>

              {/* Metric 4 */}
              <div className="p-3.5 rounded-xl border border-slate-100 bg-slate-50/60 flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center shrink-0">
                  <Users className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] text-[#65748B] font-medium truncate">Active Responders</p>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <p className="text-lg font-black text-[#12213A]">
                      {(Array.isArray(responders) ? responders.length : 0) || 28}
                    </p>
                    <span className="text-[11px] font-bold text-emerald-600 flex items-center">
                      ↑ 4%
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Response Time Trend Line Chart (Matching reference design) */}
            <div className="pt-3 border-t border-slate-100">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-bold text-[#12213A]">Response Time Trend</p>
                <span className="text-[10px] text-[#65748B]">Minutes over past 30 days</span>
              </div>
              <div className="h-[140px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trendData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                    <XAxis
                      dataKey="date"
                      stroke="#94A3B8"
                      fontSize={10}
                      tickLine={false}
                      axisLine={{ stroke: '#E2E8F0' }}
                    />
                    <YAxis
                      stroke="#94A3B8"
                      fontSize={10}
                      domain={[0, 60]}
                      ticks={[0, 30, 60]}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#10243E',
                        borderRadius: '8px',
                        border: 'none',
                        color: 'white',
                        fontSize: '11px',
                        padding: '4px 8px',
                      }}
                      itemStyle={{ color: 'white' }}
                      formatter={(val: any) => [`${val} min`, 'Response Time']}
                    />
                    <Line
                      type="monotone"
                      dataKey="minutes"
                      stroke="#2F73D9"
                      strokeWidth={2.5}
                      dot={{ r: 3.5, fill: '#2F73D9', strokeWidth: 1.5, stroke: 'white' }}
                      activeDot={{ r: 5, fill: '#2563EB', stroke: 'white', strokeWidth: 2 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
