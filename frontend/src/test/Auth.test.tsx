import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { Login } from '../pages/Login';
import { Register } from '../pages/Register';
import api from '../services/api';
import { AuthProvider } from '../context/AuthContext';

// Mock API
vi.mock('../services/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

describe('Authentication Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe('Login Component', () => {
    it('renders login form inputs and submit button', () => {
      render(
        <BrowserRouter>
          <AuthProvider>
            <Login />
          </AuthProvider>
        </BrowserRouter>
      );

      expect(screen.getByText('Sign in to PawReach')).toBeInTheDocument();
      expect(screen.getByLabelText(/Email or Phone/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Sign In/i })).toBeInTheDocument();
    });

    it('submits credentials formatted for OAuth2 password grant', async () => {
      (api.post as any).mockResolvedValueOnce({
        data: {
          access_token: 'fake-access-token',
          refresh_token: 'fake-refresh-token',
          token_type: 'bearer',
        },
      });

      (api.get as any).mockResolvedValueOnce({
        data: {
          id: 'user-1',
          full_name: 'John Citizen',
          email: 'john@example.com',
          role: 'CITIZEN',
        },
      });

      render(
        <BrowserRouter>
          <AuthProvider>
            <Login />
          </AuthProvider>
        </BrowserRouter>
      );

      fireEvent.change(screen.getByLabelText(/Email or Phone/i), {
        target: { value: 'john@example.com' },
      });
      fireEvent.change(screen.getByLabelText(/Password/i), {
        target: { value: 'secret123' },
      });

      fireEvent.click(screen.getByRole('button', { name: /Sign In/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith(
          '/auth/login',
          expect.any(URLSearchParams),
          expect.objectContaining({
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          })
        );
      });
    });
  });

  describe('Register Component', () => {
    it('does not expose role selection dropdown and enforces citizen registration', () => {
      render(
        <BrowserRouter>
          <Register />
        </BrowserRouter>
      );

      expect(screen.getByText('Create an Account')).toBeInTheDocument();
      expect(screen.queryByLabelText(/Role/i)).not.toBeInTheDocument();
      expect(screen.queryByText('ADMIN')).not.toBeInTheDocument();
      expect(screen.queryByText('RESCUER')).not.toBeInTheDocument();
    });

    it('rejects passwords that do not match before calling backend', async () => {
      render(
        <BrowserRouter>
          <Register />
        </BrowserRouter>
      );

      fireEvent.change(screen.getByLabelText(/Full Name/i), {
        target: { value: 'New User' },
      });
      fireEvent.change(screen.getByLabelText(/Email Address/i), {
        target: { value: 'user@example.com' },
      });
      fireEvent.change(screen.getByLabelText(/Phone Number/i), {
        target: { value: '+919876543210' },
      });
      fireEvent.change(screen.getByLabelText(/^Password/i), {
        target: { value: 'pass123' },
      });
      fireEvent.change(screen.getByLabelText(/Confirm Password/i), {
        target: { value: 'pass456' },
      });

      fireEvent.click(screen.getByRole('button', { name: /Sign Up/i }));

      expect(screen.getByText('Passwords do not match')).toBeInTheDocument();
      expect(api.post).not.toHaveBeenCalled();
    });
  });
});
