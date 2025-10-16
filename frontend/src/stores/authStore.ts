/**
 * Auth state management using Zustand.
 */

import { create } from 'zustand';
import type { User } from '../types';
import { authAPI } from '../api/auth';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string, password_confirm: string) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: authAPI.isAuthenticated(),
  isLoading: false,
  error: null,

  login: async (username, password) => {
    set({ isLoading: true, error: null });
    try {
      await authAPI.login({ username, password });
      const user = await authAPI.getCurrentUser();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || 'Login failed',
        isLoading: false
      });
      throw error;
    }
  },

  register: async (username, email, password, password_confirm) => {
    set({ isLoading: true, error: null });
    try {
      const data = await authAPI.register({ username, email, password, password_confirm });
      set({ user: data.user, isAuthenticated: true, isLoading: false });
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || 'Registration failed',
        isLoading: false
      });
      throw error;
    }
  },

  logout: () => {
    authAPI.logout();
    set({ user: null, isAuthenticated: false });
  },

  loadUser: async () => {
    if (!authAPI.isAuthenticated()) {
      return;
    }

    set({ isLoading: true });
    try {
      const user = await authAPI.getCurrentUser();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (error) {
      authAPI.logout();
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
