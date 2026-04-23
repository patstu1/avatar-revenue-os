import { api } from './api';

export const affiliateIntelApi = {
  offers: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/affiliate-offers`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/affiliate-offers/recompute`),
  links: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/affiliate-links`),
  leaks: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/affiliate-leaks`),
  blockers: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/affiliate-blockers`),
  ranking: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/affiliate-ranking`),
  commissions: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/affiliate-commissions`),
  payouts: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/affiliate-payouts`),
  syncNetworks: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/affiliate-sync`),
};
