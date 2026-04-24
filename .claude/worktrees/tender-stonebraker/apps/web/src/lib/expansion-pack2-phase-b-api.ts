import { api } from './api';

export const expansionPack2PhaseBApi = {
  pricingRecommendations: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/pricing-recommendations`),
  recomputePricingRecommendations: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/pricing-recommendations/recompute`),
  bundleRecommendations: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/bundle-recommendations`),
  recomputeBundleRecommendations: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/bundle-recommendations/recompute`),
  retentionRecommendations: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/retention-recommendations`),
  recomputeRetentionRecommendations: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/retention-recommendations/recompute`),
  reactivationCampaigns: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/reactivation-campaigns`),
  recomputeReactivationCampaigns: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/reactivation-campaigns/recompute`),
};
