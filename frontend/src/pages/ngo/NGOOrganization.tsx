import React, { useState, useEffect } from 'react';
import {
  Landmark,
  Building2,
  Users,
  MapPin,
  Phone,
  ShieldCheck,
  CheckCircle2,
  Save,
  AlertCircle,
  RotateCw,
} from 'lucide-react';
import api, { formatApiError } from '../../services/api';
import type { OrganizationProfile, OrganizationProfileUpdate } from '../../types';

export const NGOOrganization: React.FC = () => {
  const [profile, setProfile] = useState<OrganizationProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form fields
  const [formData, setFormData] = useState<OrganizationProfileUpdate>({
    name: '',
    phone: '',
    operating_region: '',
    address: '',
    description: '',
  });

  const fetchProfile = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get('/ngo/organization');
      const data: OrganizationProfile = res.data;
      setProfile(data);
      setFormData({
        name: data.name || '',
        phone: data.phone || '',
        operating_region: data.operating_region || '',
        address: data.address || '',
        description: data.description || '',
      });
    } catch (err: any) {
      console.error('Failed to load organization profile', err);
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setError(null);
      setSuccessMsg(null);
      const res = await api.patch('/ngo/organization', formData);
      setProfile(res.data);
      setSuccessMsg('Organization profile updated and audited successfully.');
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: any) {
      console.error('Failed to update organization profile', err);
      setError(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px] text-slate-500">
        <RotateCw className="w-6 h-6 animate-spin mr-2" /> Loading organization details...
      </div>
    );
  }

  return (
    <div className="max-w-5xl space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl border border-[#E4EAF2] shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-2xl bg-blue-50 text-blue-600">
            <Landmark className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-black text-[#12213A] tracking-tight">
                {profile?.name || 'Organization Profile'}
              </h2>
              {profile?.is_active && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-xs font-bold border border-emerald-200">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Verified NGO
                </span>
              )}
            </div>
            <p className="text-xs text-[#65748B] mt-0.5">
              Authoritative command jurisdiction and team management.
            </p>
          </div>
        </div>

        <button
          onClick={fetchProfile}
          className="p-2 self-start sm:self-auto rounded-lg text-slate-500 hover:text-blue-600 hover:bg-slate-50 transition-colors"
          title="Reload profile"
        >
          <RotateCw className="w-4 h-4" />
        </button>
      </div>

      {/* Notifications */}
      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-semibold flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <p className="text-2xl font-black text-[#12213A]">{profile?.responders_count ?? 0}</p>
            <p className="text-xs text-[#65748B] font-medium">Registered Responders</p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center shrink-0">
            <Building2 className="w-6 h-6" />
          </div>
          <div>
            <p className="text-2xl font-black text-[#12213A]">{profile?.veterinary_partners_count ?? 0}</p>
            <p className="text-xs text-[#65748B] font-medium">Partner Clinics</p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-[#E4EAF2] shadow-2xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
            <MapPin className="w-6 h-6" />
          </div>
          <div className="min-w-0">
            <p className="text-base font-extrabold text-[#12213A] truncate">
              {profile?.operating_region || 'Central Command'}
            </p>
            <p className="text-xs text-[#65748B] font-medium">Primary Operating Region</p>
          </div>
        </div>
      </div>

      {/* Edit Form */}
      <form onSubmit={handleSave} className="bg-white p-6 rounded-2xl border border-[#E4EAF2] shadow-sm space-y-5">
        <div className="pb-3 border-b border-slate-100 flex items-center justify-between">
          <h3 className="font-extrabold text-sm text-[#12213A]">
            Organization Profile & Operational Telemetry
          </h3>
          <span className="text-[11px] text-slate-400">Strictly Tenant-Scoped</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="org_name" className="block text-xs font-bold text-slate-700 mb-1">
              Organization Name
            </label>
            <input
              id="org_name"
              type="text"
              value={formData.name || ''}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label htmlFor="operating_region" className="block text-xs font-bold text-slate-700 mb-1">
              Operating Region / Jurisdiction
            </label>
            <input
              id="operating_region"
              type="text"
              value={formData.operating_region || ''}
              onChange={(e) => setFormData({ ...formData, operating_region: e.target.value })}
              placeholder="e.g. Ernakulam District & Kochi Metro"
              className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label htmlFor="hotline_phone" className="block text-xs font-bold text-slate-700 mb-1">
              Emergency Dispatch Hotline
            </label>
            <div className="relative">
              <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                id="hotline_phone"
                type="tel"
                value={formData.phone || ''}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                placeholder="+91 98470 00000"
                className="w-full pl-9 pr-3.5 py-2 rounded-xl border border-slate-200 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div>
            <label htmlFor="address_text" className="block text-xs font-bold text-slate-700 mb-1">
              Command Center Address
            </label>
            <div className="relative">
              <MapPin className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                id="address_text"
                type="text"
                value={formData.address || ''}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                placeholder="Physical headquarters or dispatch base"
                className="w-full pl-9 pr-3.5 py-2 rounded-xl border border-slate-200 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        <div>
          <label htmlFor="mandate_description" className="block text-xs font-bold text-slate-700 mb-1">
            Operational Overview & Mission Mandate
          </label>
          <textarea
            id="mandate_description"
            rows={3}
            value={formData.description || ''}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Describe your organization's ambulance coverage, fleet capabilities, and triage response scope..."
            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
        </div>

        <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
          <span className="text-[11px] text-slate-400">
            Modifications will be logged in the immutable system audit trail.
          </span>
          <button
            type="submit"
            disabled={saving}
            className="px-5 py-2 bg-blue-600 text-white rounded-xl text-xs font-bold hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1.5 shadow-sm transition-all"
          >
            {saving ? (
              <>
                <RotateCw className="w-3.5 h-3.5 animate-spin" /> Saving...
              </>
            ) : (
              <>
                <Save className="w-3.5 h-3.5" /> Save Changes
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
