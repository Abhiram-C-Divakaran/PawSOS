import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Zap,
  RotateCw,
  Award,
  HeartHandshake,
  FileBarChart,
  Calendar,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import api from '../../services/api';
import type {
  NGOOverviewKPIs,
  ResponseTimeDataPoint,
  RescueOutcomesData,
  HotspotItem,
  NGOInsightsData,
} from '../../types';

export const NGOAnalytics: React.FC = () => {
  const [period, setPeriod] = useState<'7d' | '30d' | '90d'>('30d');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [overview, setOverview] = useState<NGOOverviewKPIs | null>(null);
  const [responseTimes, setResponseTimes] = useState<ResponseTimeDataPoint[]>([]);
  const [outcomes, setOutcomes] = useState<RescueOutcomesData | null>(null);
  const [hotspots, setHotspots] = useState<HotspotItem[]>([]);
  const [insights, setInsights] = useState<NGOInsightsData | null>(null);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      setError(null);
      const [overRes, timeRes, outRes, hotRes, insRes] = await Promise.all([
        api.get('/ngo/analytics/overview'),
        api.get(`/ngo/analytics/response-times?period=${period}`),
        api.get('/ngo/analytics/outcomes'),
        api.get('/ngo/analytics/hotspots'),
        api.get('/ngo/analytics/insights'),
      ]);

      setOverview(overRes.data);
      setResponseTimes(Array.isArray(timeRes.data) ? timeRes.data : []);
      setOutcomes(outRes.data);
      setHotspots(Array.isArray(hotRes.data) ? hotRes.data : []);
      setInsights(insRes.data);
    } catch (err: any) {
      console.error('Failed to load analytics', err);
      setError('Unable to load authoritative analytics telemetry. Please verify backend connectivity.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, [period]);

  const chartData = responseTimes.map((item) => ({
    date: item.date.length > 5 ? item.date.slice(5) : item.date,
    minutes: item.avg_response_minutes,
    cases: item.cases,
  }));

  const outcomeColors = ['#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#8B5CF6'];

  return (
    <div className="space-y-6">
      {/* Top Header & Period Filter */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-blue-50 text-blue-600">
              <FileBarChart className="w-5 h-5" />
            </span>
            <div>
              <h2 className="text-xl font-black text-[#12213A] tracking-tight">
                Operations & Impact Analytics
              </h2>
              <p className="text-xs text-[#65748B]">
                Authoritative mission telemetry, outcomes, and dispatch escalation metrics.
              </p>
            </div>
          </div>
        </div>

        {/* Period Selector */}
        <div className="flex items-center gap-2 self-start sm:self-auto bg-slate-100 p-1 rounded-xl">
          {(['7d', '30d', '90d'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                period === p
                  ? 'bg-white text-blue-600 shadow-xs'
                  : 'text-[#65748B] hover:text-[#12213A]'
              }`}
            >
              {p === '7d' ? '7 Days' : p === '30d' ? '30 Days' : '90 Days'}
            </button>
          ))}
          <button
            onClick={fetchAnalytics}
            className="p-1.5 text-slate-500 hover:text-blue-600 rounded-lg hover:bg-white transition-colors"
            title="Refresh analytics data"
          >
            <RotateCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchAnalytics}
            className="px-3 py-1 bg-red-600 text-white rounded-lg text-xs font-bold hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      )}

      {/* Top 4 KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#65748B] font-semibold">Total Missions</span>
            <span className="p-2 rounded-lg bg-blue-50 text-blue-600">
              <TrendingUp className="w-4 h-4" />
            </span>
          </div>
          <p className="text-3xl font-black text-[#12213A] mt-2">
            {loading ? '—' : (overview?.total_cases ?? 0)}
          </p>
          <p className="text-[11px] text-[#65748B] mt-1">Total recorded incidents</p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#65748B] font-semibold">Avg Response Time</span>
            <span className="p-2 rounded-lg bg-amber-50 text-amber-600">
              <Clock className="w-4 h-4" />
            </span>
          </div>
          <p className="text-3xl font-black text-[#12213A] mt-2">
            {loading ? '—' : (overview?.avg_response_minutes ?? 0)} <span className="text-sm font-semibold text-slate-500">min</span>
          </p>
          <p className="text-[11px] text-[#65748B] mt-1">Triage to arrival at scene</p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#65748B] font-semibold">Rescue Success Rate</span>
            <span className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
              <CheckCircle2 className="w-4 h-4" />
            </span>
          </div>
          <p className="text-3xl font-black text-[#12213A] mt-2">
            {loading ? '—' : (outcomes?.rescue_success_rate ?? 0)}<span className="text-sm font-semibold text-slate-500">%</span>
          </p>
          <p className="text-[11px] text-[#65748B] mt-1">Cases safely resolved / treated</p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[#65748B] font-semibold">Fleet Offer Acceptance</span>
            <span className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
              <Award className="w-4 h-4" />
            </span>
          </div>
          <p className="text-3xl font-black text-[#12213A] mt-2">
            {loading ? '—' : (insights?.responder_acceptance_rate_pct ?? 0)}<span className="text-sm font-semibold text-slate-500">%</span>
          </p>
          <p className="text-[11px] text-[#65748B] mt-1">Responders accepting offers</p>
        </div>
      </div>

      {/* Middle Grid: Response Time Area Chart + Outcomes Card */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Response Time Chart */}
        <div className="lg:col-span-8 bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-[#10243E]" />
                <h3 className="font-extrabold text-sm text-[#12213A]">
                  Response Latency Trend ({period.toUpperCase()})
                </h3>
              </div>
              <span className="text-[11px] font-semibold text-slate-400">
                Authoritative Daily Aggregations
              </span>
            </div>

            <div className="h-[260px] w-full">
              {chartData.length === 0 ? (
                <div className="h-full flex items-center justify-center text-slate-400 text-xs">
                  No response time events recorded in this time period.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorMin" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#2563EB" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#2563EB" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" stroke="#94A3B8" fontSize={11} tickLine={false} />
                    <YAxis stroke="#94A3B8" fontSize={11} tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#10243E',
                        borderRadius: '8px',
                        border: 'none',
                        color: 'white',
                        fontSize: '11px',
                      }}
                      formatter={(val: any, name?: any) => [
                        name === 'minutes' ? `${val} min` : val,
                        name === 'minutes' ? 'Avg Response' : 'Cases Handled',
                      ]}
                    />
                    <Area
                      type="monotone"
                      dataKey="minutes"
                      stroke="#2563EB"
                      strokeWidth={2.5}
                      fillOpacity={1}
                      fill="url(#colorMin)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            Target SLA: Arrive within 20 minutes for critical and urgent animal distress calls.
          </p>
        </div>

        {/* Outcomes Breakdown */}
        <div className="lg:col-span-4 bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <HeartHandshake className="w-4 h-4 text-[#10243E]" />
                <h3 className="font-extrabold text-sm text-[#12213A]">
                  Rescue Outcomes
                </h3>
              </div>
              <span className="text-[11px] font-semibold text-slate-400">
                Total: {outcomes?.total_cases ?? 0}
              </span>
            </div>

            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-600 font-medium">Resolution Success</span>
                  <span className="font-bold text-emerald-600">{outcomes?.rescue_success_rate ?? 0}%</span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                    style={{ width: `${outcomes?.rescue_success_rate ?? 0}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-600 font-medium">Veterinary Handoff Rate</span>
                  <span className="font-bold text-blue-600">{outcomes?.veterinary_handoff_rate ?? 0}%</span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-blue-500 h-full rounded-full transition-all duration-500"
                    style={{ width: `${outcomes?.veterinary_handoff_rate ?? 0}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-600 font-medium">Unresolved / Unreachable</span>
                  <span className="font-bold text-red-600">{outcomes?.unresolved_rate ?? 0}%</span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-red-500 h-full rounded-full transition-all duration-500"
                    style={{ width: `${outcomes?.unresolved_rate ?? 0}%` }}
                  />
                </div>
              </div>

              {/* Status outcome items */}
              <div className="pt-2 border-t border-slate-100 space-y-2">
                {outcomes && Object.entries(outcomes.outcomes).length > 0 ? (
                  Object.entries(outcomes.outcomes).map(([statusKey, count], idx) => (
                    <div key={statusKey} className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-2 text-slate-700">
                        <span
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: outcomeColors[idx % outcomeColors.length] }}
                        />
                        {statusKey.replace(/_/g, ' ')}
                      </span>
                      <span className="font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded-md text-[11px]">
                        {count}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-400 text-center py-2">No completed cases recorded.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Grid: Spatial Hotspots + Dispatch Escalation Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Spatial Hotspots */}
        <div className="lg:col-span-6 bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-sm">
          <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Flame className="w-4 h-4 text-orange-500" />
              <h3 className="font-extrabold text-sm text-[#12213A]">
                Spatial Hotspot Clusters
              </h3>
            </div>
            <span className="text-[11px] font-semibold text-slate-400">
              High Incident Densities
            </span>
          </div>

          {hotspots.length === 0 ? (
            <div className="py-10 text-center text-slate-400 text-xs">
              No geographical incident clusters identified yet.
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {hotspots.map((h, idx) => (
                <div key={idx} className="py-3 flex items-center justify-between text-xs">
                  <div>
                    <p className="font-bold text-[#12213A]">{h.area_name || 'Geographic Cluster'}</p>
                    <p className="text-[11px] text-[#65748B]">
                      Primary species: <span className="font-medium text-slate-800">{h.top_species}</span>
                      {h.average_response_minutes ? ` · Avg arrival: ${h.average_response_minutes}m` : ''}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="px-2.5 py-1 rounded-full bg-amber-50 text-amber-800 font-black text-xs">
                      {h.incident_count} cases
                    </span>
                    {h.critical_count > 0 && (
                      <p className="text-[10px] text-red-600 font-bold mt-0.5">
                        {h.critical_count} critical
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Operational Dispatch Insights */}
        <div className="lg:col-span-6 bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-blue-600" />
                <h3 className="font-extrabold text-sm text-[#12213A]">
                  Dispatch Engine Insights
                </h3>
              </div>
              <span className="text-[11px] font-semibold text-slate-400">
                Escalation Telemetry
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                <div className="flex items-center gap-2 text-slate-500 mb-1">
                  <Calendar className="w-4 h-4" />
                  <span className="text-xs font-semibold">Busiest Day</span>
                </div>
                <p className="text-base font-extrabold text-[#12213A]">
                  {insights?.busiest_day || 'Evenly Distributed'}
                </p>
                <p className="text-[11px] text-slate-400 mt-0.5">Highest case volume</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                <div className="flex items-center gap-2 text-slate-500 mb-1">
                  <Clock className="w-4 h-4" />
                  <span className="text-xs font-semibold">Peak Window</span>
                </div>
                <p className="text-base font-extrabold text-[#12213A]">
                  {insights?.busiest_time_range || 'All Day'}
                </p>
                <p className="text-[11px] text-slate-400 mt-0.5">Peak hour cluster</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                <div className="flex items-center gap-2 text-slate-500 mb-1">
                  <Zap className="w-4 h-4" />
                  <span className="text-xs font-semibold">Avg Dispatch Attempts</span>
                </div>
                <p className="text-base font-extrabold text-[#12213A]">
                  {insights?.avg_dispatch_attempts ?? 1.0}
                </p>
                <p className="text-[11px] text-slate-400 mt-0.5">Rounds until accepted</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                <div className="flex items-center gap-2 text-slate-500 mb-1">
                  <AlertTriangle className="w-4 h-4" />
                  <span className="text-xs font-semibold">Radius Escalation Rate</span>
                </div>
                <p className="text-base font-extrabold text-[#12213A]">
                  {insights?.escalation_rate_pct ?? 0}%
                </p>
                <p className="text-[11px] text-slate-400 mt-0.5">Exceeded 5km initial radius</p>
              </div>
            </div>
          </div>

          <div className="mt-4 p-3 rounded-xl bg-blue-50/70 border border-blue-100 text-xs text-blue-800">
            <span className="font-bold">Recommendation: </span>
            {insights?.escalation_rate_pct && insights.escalation_rate_pct > 25
              ? 'High radius escalation detected. Consider onboarding additional volunteer responders in outlying zones.'
              : 'Dispatch match latency is optimal. Responders in the initial 5 km zone are actively accepting missions.'}
          </div>
        </div>
      </div>
    </div>
  );
};
