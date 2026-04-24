import { api } from './api';

export const revenueIntelApi = {
  recompute: (brandId: string) => api.post(`/api/v1/brands/${brandId}/revenue-intel/recompute`),
  dashboard: (brandId: string) => api.get('/api/v1/dashboard/revenue-intel', { params: { brand_id: brandId } }),
  offerStacks: (brandId: string) => api.get(`/api/v1/brands/${brandId}/offer-stacks`),
  funnelPaths: (brandId: string) => api.get(`/api/v1/brands/${brandId}/funnel-paths`),
  ownedAudience: (brandId: string) => api.get(`/api/v1/brands/${brandId}/owned-audience-value`),
  productization: (brandId: string) => api.get(`/api/v1/brands/${brandId}/productization`),
  monetizationDensity: (brandId: string) => api.get(`/api/v1/brands/${brandId}/monetization-density`),
};
