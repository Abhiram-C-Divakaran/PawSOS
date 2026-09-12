import type { ReactElement } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Layout } from './components/Layout';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { ReportRescue } from './pages/ReportRescue';
import { MyCases } from './pages/MyCases';
import { CaseTracking } from './pages/CaseTracking';
import { RescuerDashboard } from './pages/RescuerDashboard';
import { VetDashboard } from './pages/VetDashboard';
import { NGOLayout } from './pages/ngo/NGOLayout';
import { NGOOverview } from './pages/ngo/NGOOverview';
import { NGOCases } from './pages/ngo/NGOCases';
import { NGOCaseDetail } from './pages/ngo/NGOCaseDetail';
import { NGOResponders } from './pages/ngo/NGOResponders';
import { NGOVeterinary } from './pages/ngo/NGOVeterinary';

const ProtectedRoute = ({ children, allowedRoles }: { children: ReactElement, allowedRoles?: string[] }) => {
  const { isAuthenticated, user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>;
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
  
  if (loading) return <div>Loading...</div>;
  
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

            {/* NGO Command Center Routes */}
            <Route
              path="ngo"
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
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
