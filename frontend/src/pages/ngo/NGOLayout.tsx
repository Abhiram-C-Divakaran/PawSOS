import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, FileText, Users, Building2, ShieldCheck } from 'lucide-react';

export const NGOLayout: React.FC = () => {
  const navItems = [
    { to: '/ngo', end: true, label: 'Overview & Live Map', icon: LayoutDashboard },
    { to: '/ngo/cases', end: false, label: 'Rescue Cases', icon: FileText },
    { to: '/ngo/responders', end: false, label: 'Responder Fleet', icon: Users },
    { to: '/ngo/veterinary', end: false, label: 'Partner Clinics', icon: Building2 },
  ];

  return (
    <div className="space-y-6">
      {/* Top NGO Banner */}
      <div className="bg-gradient-to-r from-stone-900 via-stone-800 to-amber-950 text-white rounded-2xl p-6 shadow-xl border border-stone-800 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 bg-amber-500/20 text-amber-400 rounded-lg border border-amber-500/30">
              <ShieldCheck className="w-5 h-5" />
            </span>
            <h1 className="text-xl sm:text-2xl font-black tracking-tight">
              NGO Operations Command Center
            </h1>
          </div>
          <p className="text-stone-300 text-xs sm:text-sm mt-1">
            Real-time automatic dispatch management, incident clustering, and field fleet coordination.
          </p>
        </div>

        {/* Subnav Tabs */}
        <div className="flex items-center gap-1.5 p-1 bg-stone-950/60 rounded-xl border border-stone-700/50 overflow-x-auto max-w-full">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${
                    isActive
                      ? 'bg-amber-500 text-stone-950 shadow-md'
                      : 'text-stone-300 hover:text-white hover:bg-stone-800/60'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </NavLink>
            );
          })}
        </div>
      </div>

      {/* Child Route Container */}
      <Outlet />
    </div>
  );
};
