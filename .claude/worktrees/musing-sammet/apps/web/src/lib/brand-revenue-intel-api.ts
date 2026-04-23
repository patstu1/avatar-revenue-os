import { api } from './api';

export const brandRevenueIntelApi = {
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/revenue-intel/recompute`),
  offerStacks: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/offer-stacks`),
  funnelPaths: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/funnel-paths`),
  ownedAudienceValue: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/owned-audience-value`),
  productization: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/productization`),
  monetizationDensity: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/monetization-density`),
};
