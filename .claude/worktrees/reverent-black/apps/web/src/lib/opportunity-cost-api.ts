import { api } from './api';

export const opportunityCostApi = {
  reports: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/opportunity-cost`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/opportunity-cost/recompute`),
  rankedActions: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/opportunity-cost/ranked-actions`),
};
