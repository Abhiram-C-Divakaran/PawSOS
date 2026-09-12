import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  Users,
  Building2,
  TrendingUp,
  Landmark,
  Settings,
  Menu,
  X,
  LogOut,
  ChevronDown,
  Shield,
  Heart,
  CheckCircle,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { NotificationBell } from '../../components/NotificationBell';
import api from '../../services/api';
import type { OrganizationProfile } from '../../types';

export const NGOLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);
  const [orgProfile, setOrgProfile] = useState<OrganizationProfile | null>(null);

  useEffect(() => {
    let isMounted = true;
    const loadOrg = async () => {
      try {
        const res = await api.get('/ngo/organization');
        if (isMounted && res.data) {
          setOrgProfile(res.data);
        }
      } catch {
        // Silently fall back if organization is not yet linked
      }
    };
    loadOrg();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/ngo', end: true, label: 'Overview', icon: LayoutDashboard },
    { to: '/ngo/cases', end: false, label: 'Cases', icon: FileText },
    { to: '/ngo/responders', end: false, label: 'Responders', icon: Users },
    { to: '/ngo/veterinary', end: false, label: 'Veterinary Partners', icon: Building2 },
    { to: '/ngo/analytics', end: false, label: 'Analytics', icon: TrendingUp },
    { to: '/ngo/organization', end: false, label: 'Organization', icon: Landmark },
    { to: '/ngo/settings', end: false, label: 'Settings', icon: Settings },
  ];

  // Authoritative organization and user names with zero fake fallbacks
  const orgName = orgProfile?.name || (user?.organization_id ? 'Organization' : 'Command Center');
  const userName = user?.full_name || 'Admin';

  const renderSidebarContent = () => (
    <div className="flex flex-col h-full justify-between p-5 text-white">
      {/* Top Branding */}
      <div>
        <div className="flex items-center gap-3 px-2 py-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#2563EB] to-[#38BDF8] flex items-center justify-center shadow-lg shadow-blue-500/20">
            <svg
              className="w-6 h-6 text-white fill-current"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <circle cx="7" cy="8.5" r="2" />
              <circle cx="12" cy="6" r="2" />
              <circle cx="17" cy="8.5" r="2" />
              <circle cx="5" cy="13.5" r="1.7" />
              <circle cx="19" cy="13.5" r="1.7" />
              <path d="M12 11.5c-3.2 0-5.8 2.2-5.8 5.2 0 1.9 1.4 3.3 3.3 3.3.9 0 1.7-.3 2.5-1 .8.7 1.6 1 2.5 1 1.9 0 3.3-1.4 3.3-3.3 0-3-2.6-5.2-5.8-5.2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight text-white flex items-center gap-1 leading-none">
              PawReach
            </h1>
            <p className="text-[11px] text-[#8E9EB5] font-medium tracking-wide mt-1 uppercase">
              NGO Operations
            </p>
          </div>
        </div>

        {/* Navigation List */}
        <nav className="space-y-1.5" aria-label="NGO Command Navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isCurrentPage = item.end
              ? location.pathname === item.to
              : location.pathname.startsWith(item.to);

            return (
              <NavLink
                key={item.label}
                to={item.to}
                end={item.end}
                onClick={() => setMobileMenuOpen(false)}
                className={() => {
                  return `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                    isCurrentPage
                      ? 'bg-[#2F73D9] text-white shadow-md shadow-blue-900/40'
                      : 'text-[#8E9EB5] hover:text-white hover:bg-white/5'
                  }`;
                }}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Sidebar Footer Badge */}
      <div className="pt-6 border-t border-white/10 space-y-3">
        <div className="bg-[#0C1D34]/80 rounded-2xl p-4 border border-white/5 flex items-center gap-3 shadow-inner">
          <div className="w-8 h-8 rounded-full bg-[#2F73D9] flex items-center justify-center shrink-0 shadow-md">
            <Heart className="w-4 h-4 text-white fill-current" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-white leading-tight">
              Saving lives,
            </p>
            <p className="text-[11px] text-[#8E9EB5] truncate">
              one rescue at a time.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between px-2 text-[11px] text-[#8E9EB5]">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            System Online
          </span>
          <span className="font-mono text-[10px] opacity-70">v2.6 Pilot</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen flex bg-[#F5F8FC] text-[#12213A] font-sans antialiased selection:bg-blue-500 selection:text-white">
      {/* Desktop Left Sidebar */}
      <aside className="w-64 shrink-0 hidden lg:block bg-[#10243E] min-h-screen sticky top-0 h-screen overflow-y-auto border-r border-[#0C1D34]/40 z-40">
        {renderSidebarContent()}
      </aside>

      {/* Mobile Drawer Backdrop & Sidebar */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="relative w-72 max-w-[80vw] bg-[#10243E] h-full shadow-2xl flex flex-col z-10 animate-in slide-in-from-left duration-200">
            <div className="absolute top-4 right-4">
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="p-1.5 rounded-lg text-[#8E9EB5] hover:text-white hover:bg-white/10"
                aria-label="Close sidebar"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            {renderSidebarContent()}
          </div>
        </div>
      )}

      {/* Main Workspace Area */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen bg-[#F5F8FC]">
        {/* White Application Header */}
        <header className="h-20 bg-white border-b border-[#E4EAF2] px-6 lg:px-8 flex items-center justify-between sticky top-0 z-30 shadow-xs">
          {/* Left Greeting & Context */}
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="p-2 -ml-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 lg:hidden"
              aria-label="Open sidebar navigation"
            >
              <Menu className="w-5 h-5" />
            </button>

            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-[11px] font-bold tracking-wide uppercase">
                  <Shield className="w-3 h-3 text-blue-600" /> NGO Operations
                </span>
              </div>
              <h2 className="text-lg sm:text-xl font-extrabold text-[#12213A] truncate mt-0.5 tracking-tight">
                Good day, {orgName}
              </h2>
              <p className="text-xs text-[#65748B] hidden sm:block truncate">
                Real-time situational command and telemetry.
              </p>
            </div>
          </div>

          {/* Right Controls & Profile */}
          <div className="flex items-center gap-3 sm:gap-4 shrink-0">
            {/* Organization Selector Pill */}
            <button
              onClick={() => navigate('/ngo/organization')}
              className="hidden md:flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold shadow-2xs hover:bg-emerald-100 transition-colors"
              title="View Organization Profile"
            >
              <CheckCircle className="w-3.5 h-3.5 text-emerald-600 fill-emerald-100" />
              <span className="max-w-[150px] truncate">Org: {orgName}</span>
              <ChevronDown className="w-3 h-3 text-emerald-700 opacity-60 ml-0.5" />
            </button>

            {/* Notification Bell */}
            <NotificationBell variant="light" />

            {/* User Profile Dropdown / Card */}
            <div className="flex items-center gap-3 pl-2 border-l border-slate-200">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white font-bold text-xs flex items-center justify-center ring-2 ring-blue-100 shadow-sm">
                {userName
                  .split(' ')
                  .map((n) => n[0])
                  .slice(0, 2)
                  .join('')
                  .toUpperCase() || 'AD'}
              </div>
              <div className="hidden sm:block text-left">
                <p className="text-xs font-bold text-[#12213A] leading-none">
                  {userName}
                </p>
                <p className="text-[11px] text-[#65748B] font-medium mt-0.5">
                  {user?.role === 'SUPER_ADMIN' ? 'Super Admin' : 'NGO Admin'}
                </p>
              </div>

              {/* Logout action */}
              <button
                onClick={handleLogout}
                className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors ml-1"
                title="Sign out of NGO Operations"
                aria-label="Log out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </header>

        {/* Dynamic Route Content */}
        <main className="p-6 lg:p-7 flex-1 space-y-6 max-w-full overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
