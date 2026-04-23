import { api } from './api';

export type GrowthIntelDashboard = {
  brand_id: string;
  audience_segments: Array<{
    id: string;
    name: string;
    description?: string | null;
    segment_criteria?: Record<string, unknown> | null;
    estimated_size: number;
    revenue_contribution: number;
    conversion_rate: number;
    avg_ltv: number;
    platforms?: unknown;
    is_active: boolean;
  }>;
  ltv_models: Array<{
    id: string;
    segment_name: string;
    model_type: string;
    parameters?: Record<string, unknown> | null;
    estimated_ltv_30d: number;
    estimated_ltv_90d: number;
    estimated_ltv_365d: number;
    confidence: number;
    sample_size: number;
    last_trained_at?: string | null;
    is_active: boolean;
  }>;
  leaks: {
    brand_id: string;
    funnel: Record<string, unknown>;
    leaks: Array<{
      id: string;
      leak_type: string;
      affected_entity_type: string;
      affected_entity_id?: string | null;
      estimated_leaked_revenue: number;
      estimated_recoverable: number;
      root_cause?: string | null;
      recommended_fix?: string | null;
      severity: string;
      details?: Record<string, unknown> | null;
    }>;
    summary: Record<string, unknown>;
  };
  expansion: {
    geo_language_recommendations: Array<{
      id: string;
      target_geography: string;
      target_language: string;
      target_platform?: string | null;
      estimated_audience_size: number;
      estimated_revenue_potential: number;
      entry_cost_estimate: number;
      rationale?: string | null;
      confidence: string;
    }>;
    cross_platform_flow_plans: Array<Record<string, unknown>>;
    latest_expansion_decision_id?: string | null;
  };
  paid_amplification: {
    jobs: Array<{
      id: string;
      content_item_id: string;
      platform: string;
      budget: number;
      spent: number;
      status: string;
      roi: number;
      explanation?: string | null;
      is_candidate: boolean;
    }>;
    note: string;
  };
  trust_signals: {
    reports: Array<{
      id: string;
      creator_account_id?: string | null;
      trust_score: number;
      components: Record<string, number>;
      recommendations: string[];
      evidence: Record<string, unknown>;
      confidence_label: string;
    }>;
  };
};

export const growthApi = {
  growthIntel: (brandId: string) =>
    api.get<GrowthIntelDashboard>('/api/v1/dashboard/growth-intel', { params: { brand_id: brandId } }),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/growth-intel/recompute`),
  leaksOnly: (brandId: string) =>
    api.get<GrowthIntelDashboard['leaks']>('/api/v1/dashboard/leaks', { params: { brand_id: brandId } }),
  audienceSegments: (brandId: string) => api.get(`/api/v1/brands/${brandId}/audience-segments`),
  ltv: (brandId: string) => api.get(`/api/v1/brands/${brandId}/ltv`),
  expansion: (brandId: string) => api.get(`/api/v1/brands/${brandId}/expansion-recommendations`),
  paidAmplification: (brandId: string) => api.get(`/api/v1/brands/${brandId}/paid-amplification`),
  trustSignals: (brandId: string) => api.get(`/api/v1/brands/${brandId}/trust-signals`),
};
