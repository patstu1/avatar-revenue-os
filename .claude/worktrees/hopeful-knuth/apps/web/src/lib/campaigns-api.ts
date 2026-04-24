import { api } from './api';

export const campaignsApi = {
  list: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/campaigns`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/campaigns/recompute`),
  variants: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/campaign-variants`),
  blockers: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/campaign-blockers`),
};
