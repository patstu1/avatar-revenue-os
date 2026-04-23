import { api } from './api';

const base = (brandId: string) => `/api/v1/brands/${brandId}/studio`;

export const cinemaStudioApi = {
  // Projects
  listProjects: (brandId: string, status?: string) =>
    api.get(`${base(brandId)}/projects`, { params: { status } }),
  getProject: (brandId: string, id: string) =>
    api.get(`${base(brandId)}/projects/${id}`),
  createProject: (brandId: string, data: any) =>
    api.post(`${base(brandId)}/projects`, data),
  updateProject: (brandId: string, id: string, data: any) =>
    api.put(`${base(brandId)}/projects/${id}`, data),
  deleteProject: (brandId: string, id: string) =>
    api.delete(`${base(brandId)}/projects/${id}`),

  // Scenes
  listScenes: (brandId: string, projectId?: string) =>
    api.get(`${base(brandId)}/scenes`, { params: { project_id: projectId } }),
  getScene: (brandId: string, id: string) =>
    api.get(`${base(brandId)}/scenes/${id}`),
  createScene: (brandId: string, data: any) =>
    api.post(`${base(brandId)}/scenes`, data),
  updateScene: (brandId: string, id: string, data: any) =>
    api.put(`${base(brandId)}/scenes/${id}`, data),
  deleteScene: (brandId: string, id: string) =>
    api.delete(`${base(brandId)}/scenes/${id}`),
  generateFromScene: (brandId: string, sceneId: string, data?: any) =>
    api.post(`${base(brandId)}/scenes/${sceneId}/generate`, data ?? {}),

  // Characters
  listCharacters: (brandId: string) =>
    api.get(`${base(brandId)}/characters`),
  getCharacter: (brandId: string, id: string) =>
    api.get(`${base(brandId)}/characters/${id}`),
  createCharacter: (brandId: string, data: any) =>
    api.post(`${base(brandId)}/characters`, data),
  updateCharacter: (brandId: string, id: string, data: any) =>
    api.put(`${base(brandId)}/characters/${id}`, data),
  deleteCharacter: (brandId: string, id: string) =>
    api.delete(`${base(brandId)}/characters/${id}`),

  // Styles
  listStyles: (brandId: string, category?: string) =>
    api.get(`${base(brandId)}/styles`, { params: { category } }),
  createStyle: (brandId: string, data: any) =>
    api.post(`${base(brandId)}/styles`, data),
  updateStyle: (brandId: string, id: string, data: any) =>
    api.put(`${base(brandId)}/styles/${id}`, data),
  deleteStyle: (brandId: string, id: string) =>
    api.delete(`${base(brandId)}/styles/${id}`),

  // Generations
  listGenerations: (brandId: string, sceneId?: string, status?: string) =>
    api.get(`${base(brandId)}/generations`, { params: { scene_id: sceneId, status } }),
  getGeneration: (brandId: string, id: string) =>
    api.get(`${base(brandId)}/generations/${id}`),

  // Dashboard
  dashboardStats: (brandId: string) =>
    api.get(`${base(brandId)}/dashboard-stats`),
};
