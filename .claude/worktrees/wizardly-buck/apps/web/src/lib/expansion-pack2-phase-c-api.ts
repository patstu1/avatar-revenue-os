import { api } from './api';

export const expansionPack2PhaseCApi = {
  referralPrograms: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/referral-programs`),
  recomputeReferralPrograms: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/referral-programs/recompute`),
  competitiveGaps: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/competitive-gaps`),
  recomputeCompetitiveGaps: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/competitive-gaps/recompute`),
  sponsorTargets: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/sponsor-targets`),
  recomputeSponsorTargets: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/sponsor-targets/recompute`),
  sponsorOutreach: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/sponsor-outreach`),
  recomputeSponsorOutreach: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/sponsor-outreach/recompute`),
  profitGuardrails: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/profit-guardrails`),
  recomputeProfitGuardrails: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/profit-guardrails/recompute`),
};
