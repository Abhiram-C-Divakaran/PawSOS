import { useState } from 'react';
import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { LogOut, Activity, AlertCircle, ShieldPlus, Heart, Home, FileText, Menu, X } from 'lucide-react';
import { NotificationBell } from './NotificationBell';
import { NotificationPermissionBanner } from './NotificationPermissionBanner';
import { ForegroundNotificationToast } from './ForegroundNotificationToast';

export const Layout = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const handleLogout = async () => {
    setMobileNavOpen(false);
    await logout();
    navigate('/login');
  };

  const renderRoleLinks = (onNavigate?: () => void) => (
    <>
      <Link
        to="/adopt"
        onClick={onNavigate}
        className="text-gray-300 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-brightTeal px-3 py-2 rounded-md text-sm font-medium flex items-center"
      >
        <Heart className="w-4 h-4 mr-1.5 text-rose-400" /> Adopt
      </Link>

      {isAuthenticated && (
        <>
          {user?.role === 'CITIZEN' && (
            <>
              <Link
                to="/report"
                onClick={onNavigate}
                className="text-gray-300 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-brightTeal px-3 py-2 rounded-md text-sm font-medium flex items-center"
              >
                <AlertCircle className="w-4 h-4 mr-1.5" /> Report Animal
              </Link>
              <Link
                to="/my-cases"
                onClick={onNavigate}
                className="text-gray-300 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-brightTeal px-3 py-2 rounded-md text-sm font-medium flex items-center"
              >
                <Activity className="w-4 h-4 mr-1.5" /> My Cases
              </Link>
              <Link
                to="/adoption-applications"
                onClick={onNavigate}
                className="text-gray-300 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-brightTeal px-3 py-2 rounded-md text-sm font-medium flex items-center"
              >
                <FileText className="w-4 h-4 mr-1.5" /> My Applications
              </Link>
            </>
          )}
          {user?.role === 'FOSTER' && (
            <Link
              to="/foster"
              onClick={onNavigate}
              className="text-gray-300 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-brightTeal px-3 py-2 rounded-md text-sm font-medium flex items-center"
            >
              <Home className="w-4 h-4 mr-1.5 text-teal-400" /> Foster Care
            </Link>
          )}
          {user?.role === 'RESCUER' && (
            <Link
              to="/rescuer"
              onClick={onNavigate}
              className="text-gray-300 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-brightTeal px-3 py-2 rounded-md text-sm font-medium flex items-center"
            >
              <ShieldPlus className="w-4 h-4 mr-1.5" /> Rescue Dashboard
            </Link>
          )}
          {user?.role === 'VETERINARIAN' && (
            <Link
              to="/vet"
              onClick={onNavigate}
              className="text-gray-300 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-brightTeal px-3 py-2 rounded-md text-sm font-medium flex items-center"
            >
              <Activity className="w-4 h-4 mr-1.5" /> Vet Dashboard
            </Link>
          )}
          {(user?.role === 'NGO_ADMIN' || user?.role === 'SUPER_ADMIN') && (
            <Link
              to="/ngo"
              onClick={onNavigate}
              className="text-gray-300 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-brightTeal px-3 py-2 rounded-md text-sm font-medium flex items-center"
            >
              <Activity className="w-4 h-4 mr-1.5" /> NGO Command Center
            </Link>
          )}
        </>
      )}
    </>
  );

  return (
    <div className="min-h-screen bg-brand-warmBg flex flex-col overflow-x-hidden">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[60] focus:bg-brand-teal focus:text-white focus:px-4 focus:py-2 focus:rounded-lg focus:font-semibold"
      >
        Skip to main content
      </a>
      {isAuthenticated && <NotificationPermissionBanner />}
      <ForegroundNotificationToast />
      <nav className="bg-brand-darkNavy text-white shadow-md sticky top-0 z-50" aria-label="Main navigation">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <button
                type="button"
                onClick={() => setMobileNavOpen((prev) => !prev)}
                aria-label="Toggle navigation menu"
                aria-expanded={mobileNavOpen}
                className="sm:hidden mr-2 p-2 rounded-md text-gray-300 hover:text-white hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-brightTeal"
              >
                {mobileNavOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
              <Link
                to="/"
                className="flex-shrink-0 flex items-center font-bold text-xl tracking-wide text-brand-brightTeal focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-brightTeal rounded px-1"
              >
                PawReach
              </Link>

              <div className="hidden sm:ml-6 sm:flex sm:space-x-2">
                {renderRoleLinks()}
              </div>
            </div>
            <div className="flex items-center">
              {isAuthenticated ? (
                <div className="flex items-center space-x-3 sm:space-x-4">
                  <NotificationBell variant="dark" />
                  <span className="text-sm text-gray-300 hidden md:block">
                    {user?.full_name} ({user?.role})
                  </span>
                  <button
                    type="button"
                    onClick={handleLogout}
                    aria-label="Log out"
                    title="Logout"
                    className="text-gray-300 hover:text-white p-2 rounded-md flex items-center focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-brightTeal"
                  >
                    <LogOut className="w-5 h-5" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center space-x-3 sm:space-x-4">
                  <Link
                    to="/login"
                    className="text-gray-300 hover:text-white text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-brightTeal rounded px-2 py-1"
                  >
                    Log in
                  </Link>
                  <Link
                    to="/register"
                    className="bg-brand-teal hover:bg-brand-brightTeal text-white px-4 py-2 rounded-md text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-white"
                  >
                    Sign up
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileNavOpen && (
          <div className="sm:hidden border-t border-white/10 px-4 pt-2 pb-4 space-y-1 bg-brand-darkNavy">
            {renderRoleLinks(() => setMobileNavOpen(false))}
            {isAuthenticated && user && (
              <div className="pt-2 mt-2 border-t border-white/10 px-3 py-1 text-xs text-gray-400">
                Signed in as <span className="text-gray-200 font-medium">{user.full_name}</span> ({user.role})
              </div>
            )}
          </div>
        )}
      </nav>

      <main id="main-content" className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  );
};
