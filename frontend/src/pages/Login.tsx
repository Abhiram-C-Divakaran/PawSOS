import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import api from '../services/api';
import { sanitizeNotificationRoute } from '../services/firebase';
import { formatApiError } from '../utils/error';
import { AlertCircle, CheckCircle2 } from 'lucide-react';

export const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const searchRedirect = new URLSearchParams(location.search).get('redirect');
  const safeRedirect = sanitizeNotificationRoute(searchRedirect);
  const from = (location.state as any)?.from?.pathname || safeRedirect || '/';
  const successMessage = (location.state as any)?.message || '';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const formData = new URLSearchParams();
      formData.append('username', email); // OAuth2 expects 'username'
      formData.append('password', password);

      const response = await api.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });

      await login(response.data);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(formatApiError(err, 'Failed to login. Please check credentials.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-2">
      <div className="bg-white p-6 sm:p-8 rounded-xl shadow-sm border border-gray-100 w-full max-w-md">
        <h1 className="text-2xl font-bold text-brand-darkNavy mb-6 text-center">Sign in to PawReach</h1>

        {successMessage && !error && (
          <div role="status" className="mb-4 bg-emerald-50 text-emerald-700 p-3 rounded-lg text-sm flex items-start border border-emerald-200">
            <CheckCircle2 className="w-5 h-5 mr-2 flex-shrink-0 text-emerald-600" />
            <p>{successMessage}</p>
          </div>
        )}

        {error && (
          <div role="alert" className="mb-4 bg-red-50 text-red-600 p-3 rounded-lg text-sm flex items-start">
            <AlertCircle className="w-5 h-5 mr-2 flex-shrink-0" />
            <p>{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email or Phone</label>
            <input
              id="email"
              type="text"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal focus:border-transparent outline-none"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-teal focus:border-transparent outline-none"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-brand-darkNavy hover:bg-brand-deepNavy text-white font-semibold py-2.5 rounded-lg transition-colors flex justify-center items-center mt-6 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-teal disabled:opacity-50"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-600">
          Don't have an account?{' '}
          <Link to="/register" className="text-brand-teal hover:text-brand-brightTeal font-semibold">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
};
