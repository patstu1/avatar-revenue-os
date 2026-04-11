import { api } from './api';

export const accountStateIntelApi = {
  reports: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/account-state`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/account-state/recompute`),
  transitions: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/account-state/transitions`),
  actions: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/account-state/actions`),
};
