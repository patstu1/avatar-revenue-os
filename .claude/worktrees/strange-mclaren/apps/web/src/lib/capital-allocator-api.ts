import { api } from './api';

export const capitalAllocatorApi = {
  reports: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/capital-allocation/reports`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/capital-allocation/recompute`),
  decisions: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/capital-allocation/decisions`),
  rebalances: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/capital-allocation/rebalances`),
};
