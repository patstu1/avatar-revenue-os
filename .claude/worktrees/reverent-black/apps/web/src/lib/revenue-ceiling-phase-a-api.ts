import { api } from './api';

export type OfferLadder = {
  id: string;
  opportunity_key: string;
  top_of_funnel_asset: string;
  first_monetization_step: string;
  second_monetization_step: string;
  ladder_recommendation?: string | null;
  expected_first_conversion_value: number;
  expected_downstream_value: number;
  expected_ltv_contribution: number;
  friction_level: string;
  confidence: number;
  explanation?: string | null;
};

export type OwnedAudienceBundle = {
  assets: Array<{
    id: string;
    asset_type: string;
    channel_name: string;
    content_family?: string | null;
    objective_per_family?: Record<string, unknown> | null;
    cta_variants?: unknown[] | null;
    estimated_channel_value: number;
    direct_vs_capture_score: number;
  }>;
  events: Array<{
    id: string;
    content_item_id?: string | null;
    asset_id?: string | null;
    event_type: string;
    value_contribution: number;
    created_at?: string | null;
  }>;
};

export type MessageSequence = {
  id: string;
  sequence_type: string;
  channel: string;
  title: string;
  sponsor_safe: boolean;
  steps: Array<{
    id: string;
    step_order: number;
    channel: string;
    subject_or_title?: string | null;
    body_template?: string | null;
    delay_hours_after_previous: number;
  }>;
};

export type FunnelStageMetric = {
  id: string;
  content_family: string;
  stage: string;
  metric_value: number;
  sample_size: number;
};

export type FunnelLeak = {
  id: string;
  leak_type: string;
  severity: string;
  affected_funnel_stage: string;
  affected_content_family?: string | null;
  suspected_cause?: string | null;
  recommended_fix?: string | null;
  expected_upside: number;
  confidence: number;
  urgency: number;
};

export const revenueCeilingPhaseAApi = {
  offerLadders: (brandId: string) => api.get<OfferLadder[]>(`/api/v1/brands/${brandId}/offer-ladders`),
  recomputeOfferLadders: (brandId: string) => api.post(`/api/v1/brands/${brandId}/offer-ladders/recompute`),
  ownedAudience: (brandId: string) => api.get<OwnedAudienceBundle>(`/api/v1/brands/${brandId}/owned-audience`),
  recomputeOwnedAudience: (brandId: string) => api.post(`/api/v1/brands/${brandId}/owned-audience/recompute`),
  messageSequences: (brandId: string) => api.get<MessageSequence[]>(`/api/v1/brands/${brandId}/message-sequences`),
  generateSequences: (brandId: string) => api.post(`/api/v1/brands/${brandId}/message-sequences/generate`),
  funnelStageMetrics: (brandId: string) => api.get<FunnelStageMetric[]>(`/api/v1/brands/${brandId}/funnel-stage-metrics`),
  funnelLeaks: (brandId: string) => api.get<FunnelLeak[]>(`/api/v1/brands/${brandId}/funnel-leaks`),
  recomputeFunnelLeaks: (brandId: string) => api.post(`/api/v1/brands/${brandId}/funnel-leaks/recompute`),
};
