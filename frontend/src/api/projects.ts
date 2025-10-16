/**
 * Projects API service.
 */

import { apiClient } from './client';
import type { Project, Scene } from '../types';

export const projectsAPI = {
  /**
   * Get all projects for current user.
   */
  async list(): Promise<Project[]> {
    const response = await apiClient.get<{ results: Project[] }>('/projects/');
    return response.data.results;
  },

  /**
   * Get a specific project.
   */
  async get(id: string): Promise<Project> {
    const response = await apiClient.get<Project>(`/projects/${id}/`);
    return response.data;
  },

  /**
   * Create a new project.
   */
  async create(data: Partial<Project>): Promise<Project> {
    const response = await apiClient.post<Project>('/projects/', data);
    return response.data;
  },

  /**
   * Update a project.
   */
  async update(id: string, data: Partial<Project>): Promise<Project> {
    const response = await apiClient.patch<Project>(`/projects/${id}/`, data);
    return response.data;
  },

  /**
   * Delete a project.
   */
  async delete(id: string): Promise<void> {
    await apiClient.delete(`/projects/${id}/`);
  },

  /**
   * Get all scenes for a project.
   */
  async getScenes(id: string): Promise<Scene[]> {
    const response = await apiClient.get<Scene[]>(`/projects/${id}/scenes/`);
    return response.data;
  },
};
