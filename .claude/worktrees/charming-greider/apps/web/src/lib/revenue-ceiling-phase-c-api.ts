import { api } from './api';

export const revenueCeilingPhaseCApi = {
  recurringRevenue: (brandId: string) => api.get(`/api/v1/brands/${brandId}/recurring-revenue`),
  recomputeRecurringRevenue: (brandId: string) => api.post(`/api/v1/brands/${brandId}/recurring-revenue/recompute`),

  sponsorInventory: (brandId: string) => api.get(`/api/v1/brands/${brandId}/sponsor-inventory`),
  recomputeSponsorInventory: (brandId: string) => api.post(`/api/v1/brands/${brandId}/sponsor-inventory/recompute`),

  sponsorPackageRecommendations: (brandId: string) => api.get(`/api/v1/brands/${brandId}/sponsor-package-recommendations`),

  paidPromotionCandidates: (brandId: string) => api.get(`/api/v1/brands/${brandId}/paid-promotion-candidates`),
  recomputePaidPromotionCandidates: (brandId: string) => api.post(`/api/v1/brands/${brandId}/paid-promotion-candidates/recompute`),

  trustConversion: (brandId: string) => api.get(`/api/v1/brands/${brandId}/trust-conversion`),
  recomputeTrustConversion: (brandId: string) => api.post(`/api/v1/brands/${brandId}/trust-conversion/recompute`),

  monetizationMix: (brandId: string) => api.get(`/api/v1/brands/${brandId}/monetization-mix`),
  recomputeMonetizationMix: (brandId: string) => api.post(`/api/v1/brands/${brandId}/monetization-mix/recompute`),
};
