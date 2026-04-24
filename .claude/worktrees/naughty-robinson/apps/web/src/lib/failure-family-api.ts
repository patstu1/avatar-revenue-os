import { api } from './api';

export const failureFamilyApi = {
  reports: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/failure-families`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/failure-families/recompute`),
  suppressionRules: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/suppression-rules`),
  suppressionEvents: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/suppression-events`),
  decayCheck: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/failure-families/decay-check`),
};
