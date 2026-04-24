import { api } from './api';

export const causalAttributionApi = {
  reports: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/causal-attribution`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/causal-attribution/recompute`),
  hypotheses: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/causal-attribution/hypotheses`),
  credits: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/causal-attribution/credits`),
  confidence: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/causal-attribution/confidence`),
};
