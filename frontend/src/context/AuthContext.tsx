import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import api from '../services/api';
import { unregisterDeviceTokenFromBackend } from '../services/firebase';
import type { User } from '../types';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (tokenData: any) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const refreshUser = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    
    try {
      const response = await api.get('/auth/me');
      setUser(response.data);
    } catch (error) {
      console.error('Failed to fetch user:', error);
      setUser(null);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const login = async (tokenData: any) => {
    if (tokenData?.access_token) {
      localStorage.setItem('access_token', tokenData.access_token);
    }
    if (tokenData?.refresh_token) {
      localStorage.setItem('refresh_token', tokenData.refresh_token);
    } else {
      localStorage.removeItem('refresh_token');
    }
    await refreshUser();
  };

  const logout = async () => {
    try {
      await unregisterDeviceTokenFromBackend();
    } catch (e) {
      // Ignore unregister errors during logout
    }

    try {
      await api.post('/auth/logout');
    } catch (e) {
      // Continue cleanup even if server request fails
    }

    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, loading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
