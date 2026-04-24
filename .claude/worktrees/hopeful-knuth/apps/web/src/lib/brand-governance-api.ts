import { api } from './api';

export const brandGovernanceApi = {
  profiles: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/governance-profiles`),
  voiceRules: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/governance-voice-rules`),
  knowledge: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/governance-knowledge`),
  audiences: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/governance-audiences`),
  assets: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/governance-assets`),
  violations: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/governance-violations`),
  approvals: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/governance-approvals`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/governance/recompute`),
  evaluate: (brandId: string, content_item_id: string) =>
    api.post(`/api/v1/brands/${brandId}/governance/${content_item_id}/evaluate`),
};
