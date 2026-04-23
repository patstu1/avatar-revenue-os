import { api } from './api';

export const providerRegistryApi = {
  listProviders: (brandId: string) => api.get(`/api/v1/brands/${brandId}/providers`),
  listReadiness: (brandId: string) => api.get(`/api/v1/brands/${brandId}/providers/readiness`),
  listDependencies: (brandId: string) => api.get(`/api/v1/brands/${brandId}/providers/dependencies`),
  runAudit: (brandId: string) => api.post(`/api/v1/brands/${brandId}/providers/audit`),
  listBlockers: (brandId: string) => api.get(`/api/v1/brands/${brandId}/providers/blockers`),
};
