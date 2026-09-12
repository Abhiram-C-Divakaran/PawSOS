import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LogOut, Activity, AlertCircle, ShieldPlus } from 'lucide-react';
import { NotificationBell } from './NotificationBell';
import { NotificationPermissionBanner } from './NotificationPermissionBanner';
import { ForegroundNotificationToast } from './ForegroundNotificationToast';

export const Layout = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-brand-warmBg flex flex-col">
      {isAuthenticated && <NotificationPermissionBanner />}
      <ForegroundNotificationToast />
      <nav className="bg-brand-darkNavy text-white shadow-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link to="/" className="flex-shrink-0 flex items-center font-bold text-xl tracking-wide text-brand-brightTeal">
                PawReach
              </Link>
              {isAuthenticated && (
                <div className="hidden sm:ml-6 sm:flex sm:space-x-4">
                  {user?.role === 'CITIZEN' && (
                    <>
                      <Link to="/report" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium flex items-center">
                        <AlertCircle className="w-4 h-4 mr-1" /> Report Animal
                      </Link>
                      <Link to="/my-cases" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium flex items-center">
                        <Activity className="w-4 h-4 mr-1" /> My Cases
                      </Link>
                    </>
                  )}
                  {user?.role === 'RESCUER' && (
                    <Link to="/rescuer" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium flex items-center">
                      <ShieldPlus className="w-4 h-4 mr-1" /> Rescue Dashboard
                    </Link>
                  )}
                  {user?.role === 'VETERINARIAN' && (
                    <Link to="/vet" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium flex items-center">
                      <Activity className="w-4 h-4 mr-1" /> Vet Dashboard
                    </Link>
                  )}
                  {(user?.role === 'NGO_ADMIN' || user?.role === 'SUPER_ADMIN') && (
                    <Link to="/ngo" className="text-gray-300 hover:text-white px-3 py-2 rounded-md text-sm font-medium flex items-center">
                      <Activity className="w-4 h-4 mr-1" /> NGO Command Center
                    </Link>
                  )}
                </div>
              )}
            </div>
            <div className="flex items-center">
              {isAuthenticated ? (
                <div className="flex items-center space-x-4">
                  <NotificationBell />
                  <span className="text-sm text-gray-300 hidden md:block">
                    {user?.full_name} ({user?.role})
                  </span>
                  <button
                    onClick={handleLogout}
                    className="text-gray-300 hover:text-white p-2 rounded-md flex items-center"
                    title="Logout"
                  >
                    <LogOut className="w-5 h-5" />
                  </button>
                </div>
              ) : (
                <div className="space-x-4">
                  <Link to="/login" className="text-gray-300 hover:text-white text-sm font-medium">
                    Log in
                  </Link>
                  <Link to="/register" className="bg-brand-teal hover:bg-brand-brightTeal text-white px-4 py-2 rounded-md text-sm font-medium transition-colors">
                    Sign up
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
        {/* Mobile menu could go here */}
      </nav>

      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
};
