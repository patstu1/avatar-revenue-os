import { api } from './api';

export type ScaleCommandCenter = {
  brand_id: string;
  brand_name: string;
  portfolio_overview: {
    accounts: Array<Record<string, unknown>>;
    totals?: { total_revenue: number; total_profit: number; active_accounts: number };
    total_impressions_rollups: number;
    recommended_structure: string;
  };
  ai_recommendations: Array<Record<string, unknown>>;
  best_next_account: Record<string, unknown>;
  recommended_account_count: number;
  incremental_tradeoff?: {
    incremental_profit_new_account?: number;
    incremental_profit_more_volume_on_existing?: number;
    comparison_ratio_new_vs_volume?: number;
    expansion_beats_existing_threshold?: number;
    interpretation?: string;
    tradeoff_winner_hint?: string;
    primary_recommendation_id?: string | null;
  };
  audit?: {
    engine_module?: string;
    formula_constants?: Record<string, number>;
    funnel_weak_gate_current?: boolean;
    offer_diversity_weak_current?: boolean;
  };
  platform_allocation: Record<string, { pct: number; accounts: string[] }>;
  niche_expansion: Record<string, unknown>;
  revenue_leak_alerts: Array<Record<string, unknown>>;
  growth_blockers: Array<Record<string, unknown>>;
  saturation_cannibalization_warnings: Array<Record<string, unknown>>;
  weekly_action_plan: Array<{ day?: string; theme?: string; actions?: string[] }>;
  computed_at: string | null;
};

export const scaleApi = {
  commandCenter: (brandId: string) =>
    api.get<ScaleCommandCenter>('/api/v1/dashboard/scale-command-center', { params: { brand_id: brandId } }),
  listRecommendations: (brandId: string) => api.get(`/api/v1/brands/${brandId}/scale-recommendations`),
  recomputeRecommendations: (brandId: string) => api.post(`/api/v1/brands/${brandId}/scale-recommendations/recompute`),
  listAllocations: (brandId: string) => api.get(`/api/v1/brands/${brandId}/portfolio-allocations`),
  recomputeAllocations: (brandId: string) => api.post(`/api/v1/brands/${brandId}/portfolio-allocations/recompute`),
};
