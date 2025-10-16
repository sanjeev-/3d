/**
 * TypeScript type definitions for the application.
 */

export interface User {
  id: number;
  username: string;
  email: string;
  avatar?: string;
  bio?: string;
  created_at: string;
}

export interface Project {
  id: string;
  owner: number;
  owner_username: string;
  title: string;
  description: string;
  resolution_width: number;
  resolution_height: number;
  fps: number;
  duration_frames: number;
  render_engine: 'CYCLES' | 'EEVEE';
  render_samples: number;
  thumbnail?: string;
  created_at: string;
  updated_at: string;
  scenes_count: number;
}

export interface Scene {
  id: string;
  project: string;
  project_title: string;
  name: string;
  description: string;
  frame_start: number;
  frame_end: number;
  duration_frames: number;
  order: number;
  blend_file?: string;
  thumbnail?: string;
  camera_name: string;
  blend_file_version: number;
  objects: SceneObject[];
  created_at: string;
  updated_at: string;
}

export interface SceneObject {
  id: string;
  scene: string;
  object_type: 'CHARACTER' | 'ASSET' | 'LIGHT' | 'CAMERA';
  name: string;
  character?: string;
  asset?: string;
  position_x: number;
  position_y: number;
  position_z: number;
  rotation_x: number;
  rotation_y: number;
  rotation_z: number;
  scale_x: number;
  scale_y: number;
  scale_z: number;
  properties: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface Asset {
  id: string;
  project?: string;
  owner: number;
  owner_username: string;
  name: string;
  description: string;
  asset_type: 'MODEL' | 'TEXTURE' | 'MATERIAL' | 'HDRI';
  file: string;
  thumbnail?: string;
  file_size?: number;
  created_at: string;
  updated_at: string;
}

export interface Character {
  id: string;
  project?: string;
  owner: number;
  owner_username: string;
  name: string;
  description: string;
  blend_file: string;
  thumbnail?: string;
  created_at: string;
  updated_at: string;
}

export interface RenderJob {
  id: string;
  scene: string;
  scene_name: string;
  status: 'PENDING' | 'RENDERING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  preset: string;
  samples?: number;
  progress: number;
  current_frame?: number;
  output_directory: string;
  final_video?: string;
  started_at?: string;
  completed_at?: string;
  error_message: string;
  created_at: string;
  updated_at: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterData {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
}
