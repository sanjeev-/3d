/**
 * Authentication API service.
 */

import { apiClient } from './client';
import type { User, AuthTokens, LoginCredentials, RegisterData } from '../types';

export const authAPI = {
  /**
   * Login user.
   */
  async login(credentials: LoginCredentials): Promise<AuthTokens> {
    const response = await apiClient.post<AuthTokens>('/auth/login/', credentials);
    const { access, refresh } = response.data;

    // Store tokens
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);

    return response.data;
  },

  /**
   * Register new user.
   */
  async register(data: RegisterData): Promise<{ user: User; access: string; refresh: string }> {
    const response = await apiClient.post('/users/', data);
    const { user, access, refresh } = response.data;

    // Store tokens
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);

    return response.data;
  },

  /**
   * Logout user.
   */
  logout(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  },

  /**
   * Get current user.
   */
  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get<User>('/users/me/');
    return response.data;
  },

  /**
   * Check if user is authenticated.
   */
  isAuthenticated(): boolean {
    return !!localStorage.getItem('access_token');
  },
};
