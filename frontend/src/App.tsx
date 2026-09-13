import { lazy, Suspense, type ReactElement } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/useAuth';
import { Layout } from './components/Layout';
import { RouteLoadingSpinner } from './components/RouteLoadingSpinner';

// Route-level lazy loading for optimal bundle chunking and performance
const Login = lazy(() => import('./pages/Login').then((m) => ({ default: m.Login })));
const Register = lazy(() => import('./pages/Register').then((m) => ({ default: m.Register })));
const ReportRescue = lazy(() => import('./pages/ReportRescue').then((m) => ({ default: m.ReportRescue })));
const MyCases = lazy(() => import('./pages/MyCases').then((m) => ({ default: m.MyCases })));
const CaseTracking = lazy(() => import('./pages/CaseTracking').then((m) => ({ default: m.CaseTracking })));
const RescuerDashboard = lazy(() => import('./pages/RescuerDashboard').then((m) => ({ default: m.RescuerDashboard })));
const VetDashboard = lazy(() => import('./pages/VetDashboard').then((m) => ({ default: m.VetDashboard })));

// NGO Command Center Route Chunks
const NGOLayout = lazy(() => import('./pages/ngo/NGOLayout').then((m) => ({ default: m.NGOLayout })));
const NGOOverview = lazy(() => import('./pages/ngo/NGOOverview').then((m) => ({ default: m.NGOOverview })));
const NGOCases = lazy(() => import('./pages/ngo/NGOCases').then((m) => ({ default: m.NGOCases })));
const NGOCaseDetail = lazy(() => import('./pages/ngo/NGOCaseDetail').then((m) => ({ default: m.NGOCaseDetail })));
const NGOResponders = lazy(() => import('./pages/ngo/NGOResponders').then((m) => ({ default: m.NGOResponders })));
const NGOVeterinary = lazy(() => import('./pages/ngo/NGOVeterinary').then((m) => ({ default: m.NGOVeterinary })));
const NGOAnalytics = lazy(() => import('./pages/ngo/NGOAnalytics').then((m) => ({ default: m.NGOAnalytics })));
const NGOOrganization = lazy(() => import('./pages/ngo/NGOOrganization').then((m) => ({ default: m.NGOOrganization })));
const NGOSettings = lazy(() => import('./pages/ngo/NGOSettings').then((m) => ({ default: m.NGOSettings })));

const ProtectedRoute = ({ children, allowedRoles }: { children: ReactElement, allowedRoles?: string[] }) => {
  const { isAuthenticated, user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <RouteLoadingSpinner />;
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return children;
};

// Simple index redirect component
const HomeRedirect = () => {
  const { user, isAuthenticated, loading } = useAuth();
  
  if (loading) return <RouteLoadingSpinner />;
  
  if (isAuthenticated && user) {
    if (user.role === 'RESCUER') return <Navigate to="/rescuer" replace />;
    if (user.role === 'VETERINARIAN') return <Navigate to="/vet" replace />;
    if (user.role === 'NGO_ADMIN' || user.role === 'SUPER_ADMIN') return <Navigate to="/ngo" replace />;
    return <Navigate to="/my-cases" replace />;
  }
  
  return <Navigate to="/login" replace />;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<RouteLoadingSpinner />}>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<HomeRedirect />} />
              <Route path="login" element={<Login />} />
              <Route path="register" element={<Register />} />
              
              {/* Citizen Routes */}
              <Route path="report" element={<ProtectedRoute><ReportRescue /></ProtectedRoute>} />
              <Route path="my-cases" element={<ProtectedRoute><MyCases /></ProtectedRoute>} />
              <Route path="cases/:id" element={<ProtectedRoute><CaseTracking /></ProtectedRoute>} />
              
              {/* Rescuer Routes */}
              <Route path="rescuer" element={<ProtectedRoute allowedRoles={['RESCUER', 'NGO_ADMIN']}><RescuerDashboard /></ProtectedRoute>} />
              
              {/* Vet Routes */}
              <Route path="vet" element={<ProtectedRoute allowedRoles={['VETERINARIAN', 'NGO_ADMIN']}><VetDashboard /></ProtectedRoute>} />
            </Route>

            {/* Standalone NGO Command Center Application Shell */}
            <Route
              path="/ngo"
              element={
                <ProtectedRoute allowedRoles={['NGO_ADMIN', 'SUPER_ADMIN']}>
                  <NGOLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<NGOOverview />} />
              <Route path="cases" element={<NGOCases />} />
              <Route path="cases/:id" element={<NGOCaseDetail />} />
              <Route path="responders" element={<NGOResponders />} />
              <Route path="veterinary" element={<NGOVeterinary />} />
              <Route path="analytics" element={<NGOAnalytics />} />
              <Route path="organization" element={<NGOOrganization />} />
              <Route path="settings" element={<NGOSettings />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
