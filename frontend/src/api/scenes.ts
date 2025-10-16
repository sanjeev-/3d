/**
 * Scenes API service.
 */

import { apiClient } from './client';
import type { Scene, SceneObject } from '../types';

export const scenesAPI = {
  /**
   * Get all scenes for current user.
   */
  async list(): Promise<Scene[]> {
    const response = await apiClient.get<{ results: Scene[] }>('/scenes/');
    return response.data.results;
  },

  /**
   * Get a specific scene.
   */
  async get(id: string): Promise<Scene> {
    const response = await apiClient.get<Scene>(`/scenes/${id}/`);
    return response.data;
  },

  /**
   * Create a new scene.
   */
  async create(data: Partial<Scene>): Promise<Scene> {
    const response = await apiClient.post<Scene>('/scenes/', data);
    return response.data;
  },

  /**
   * Update a scene.
   */
  async update(id: string, data: Partial<Scene>): Promise<Scene> {
    const response = await apiClient.patch<Scene>(`/scenes/${id}/`, data);
    return response.data;
  },

  /**
   * Delete a scene.
   */
  async delete(id: string): Promise<void> {
    await apiClient.delete(`/scenes/${id}/`);
  },

  /**
   * Add an object to a scene.
   */
  async addObject(sceneId: string, data: Partial<SceneObject>): Promise<SceneObject> {
    const response = await apiClient.post<SceneObject>(
      `/scenes/${sceneId}/add_object/`,
      data
    );
    return response.data;
  },

  /**
   * Update an object in a scene.
   */
  async updateObject(sceneId: string, data: Partial<SceneObject>): Promise<SceneObject> {
    const response = await apiClient.post<SceneObject>(
      `/scenes/${sceneId}/update_object/`,
      data
    );
    return response.data;
  },

  /**
   * Start rendering a scene.
   */
  async render(sceneId: string, preset: string = 'medium'): Promise<any> {
    const response = await apiClient.post(`/scenes/${sceneId}/render/`, { preset });
    return response.data;
  },
};
