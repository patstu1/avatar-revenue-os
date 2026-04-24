import { api } from './api';

export const trendViralApi = {
  signals: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/trend-signals`),
  velocity: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/trend-velocity`),
  opportunities: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/viral-opportunities`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/viral-opportunities/recompute`),
  blockers: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/trend-blockers`),
  sourceHealth: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/trend-source-health`),
  topOpportunities: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/top-trend-opportunities`),
};
