import { api } from './api';

export const expansionPack2PhaseAApi = {
  leadOpportunities: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/lead-opportunities`),
  leadCloserActions: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/lead-opportunities/closer-actions`),
  leadQualification: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/lead-qualification`),
  recomputeLeadQualification: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/lead-qualification/recompute`),
  ownedOfferRecommendations: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/owned-offer-recommendations`),
  recomputeOwnedOfferRecommendations: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/owned-offer-recommendations/recompute`),
};
