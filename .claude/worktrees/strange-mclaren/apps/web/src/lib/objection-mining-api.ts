import { api } from './api';

export const objectionMiningApi = {
  signals: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/objection-signals`),
  clusters: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/objection-clusters`),
  responses: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/objection-responses`),
  priority: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/objection-priority`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/objection-mining/recompute`),
};
