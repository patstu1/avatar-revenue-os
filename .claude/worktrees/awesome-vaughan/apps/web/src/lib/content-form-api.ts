import { api } from './api';

export const contentFormApi = {
  recommendations: (brandId: string) => api.get(`/api/v1/brands/${brandId}/content-forms`),
  recomputeRecommendations: (brandId: string) => api.post(`/api/v1/brands/${brandId}/content-forms/recompute`),
  mix: (brandId: string) => api.get(`/api/v1/brands/${brandId}/content-form-mix`),
  recomputeMix: (brandId: string) => api.post(`/api/v1/brands/${brandId}/content-form-mix/recompute`),
  blockers: (brandId: string) => api.get(`/api/v1/brands/${brandId}/content-form-blockers`),
};
