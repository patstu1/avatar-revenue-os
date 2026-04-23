import { api } from './api';

export const expansionAdvisorApi = {
  advisories: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/expansion-advisor`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/expansion-advisor/recompute`),
};
