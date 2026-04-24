import { api } from './api';

export type OperatorAlert = {
  id: string;
  alert_type: string;
  title: string;
  summary: string;
  explanation?: string | null;
  recommended_action?: string | null;
  confidence: number;
  urgency: number;
  expected_upside: number;
  expected_cost: number;
  expected_time_to_signal_days: number;
  supporting_metrics?: Record<string, unknown> | null;
  blocking_factors?: unknown[] | null;
  severity?: string | null;
  dashboard_section?: string | null;
  linked_scale_recommendation_id?: string | null;
  linked_launch_candidate_id?: string | null;
  status: string;
  acknowledged_at?: string | null;
  resolved_at?: string | null;
  created_at?: string | null;
};

export type LaunchCandidate = {
  id: string;
  linked_scale_recommendation_id?: string | null;
  candidate_type: string;
  primary_platform: string;
  secondary_platform?: string | null;
  niche: string;
  sub_niche?: string | null;
  language: string;
  geography: string;
  avatar_persona_strategy?: string | null;
  monetization_path?: string | null;
  content_style?: string | null;
  posting_strategy?: string | null;
  expected_monthly_revenue_min: number;
  expected_monthly_revenue_max: number;
  expected_launch_cost: number;
  expected_time_to_signal_days: number;
  expected_time_to_profit_days: number;
  cannibalization_risk: number;
  audience_separation_score: number;
  confidence: number;
  urgency: number;
  supporting_reasons?: unknown[] | null;
  required_resources?: unknown[] | null;
  launch_blockers?: unknown[] | null;
};

export type ScaleBlocker = {
  id: string;
  blocker_type: string;
  severity: string;
  title: string;
  explanation?: string | null;
  recommended_fix?: string | null;
  current_value: number;
  threshold_value: number;
};

export type LaunchReadiness = {
  id: string;
  launch_readiness_score: number;
  explanation?: string | null;
  recommended_action: string;
  gating_factors?: unknown[] | null;
  components?: Record<string, unknown> | null;
};

export type NotificationDelivery = {
  id: string;
  alert_id?: string | null;
  channel: string;
  status: string;
  attempts: number;
  last_error?: string | null;
  delivered_at?: string | null;
};

export const scaleAlertsApi = {
  alerts: (brandId: string, params?: { status?: string; alert_type?: string; severity?: string }) =>
    api.get<OperatorAlert[]>(`/api/v1/brands/${brandId}/alerts`, { params }),
  recomputeAlerts: (brandId: string) => api.post(`/api/v1/brands/${brandId}/alerts/recompute`),
  recomputeAll: (brandId: string) => api.post(`/api/v1/brands/${brandId}/scale-intel/recompute-all`),
  acknowledge: (alertId: string) => api.post(`/api/v1/alerts/${alertId}/acknowledge`),
  resolve: (alertId: string, notes?: string) =>
    api.post(`/api/v1/alerts/${alertId}/resolve`, { notes: notes ?? null }),
  launchCandidates: (brandId: string) => api.get<LaunchCandidate[]>(`/api/v1/brands/${brandId}/launch-candidates`),
  recomputeLaunchCandidates: (brandId: string) => api.post(`/api/v1/brands/${brandId}/launch-candidates/recompute`),
  launchCandidate: (candidateId: string) => api.get<LaunchCandidate>(`/api/v1/brands/launch-candidates/${candidateId}`),
  scaleBlockers: (brandId: string) => api.get<ScaleBlocker[]>(`/api/v1/brands/${brandId}/scale-blockers`),
  recomputeBlockers: (brandId: string) => api.post(`/api/v1/brands/${brandId}/scale-blockers/recompute`),
  launchReadiness: (brandId: string) => api.get<LaunchReadiness>(`/api/v1/brands/${brandId}/launch-readiness`),
  recomputeReadiness: (brandId: string) => api.post(`/api/v1/brands/${brandId}/launch-readiness/recompute`),
  notifications: (brandId: string) => api.get<NotificationDelivery[]>(`/api/v1/brands/${brandId}/notifications`),
};
