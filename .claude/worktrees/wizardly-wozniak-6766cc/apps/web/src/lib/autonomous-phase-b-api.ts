import { api } from './api';

export async function fetchExecutionPolicies(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/execution-policies`);
  return res.data;
}

export async function recomputeExecutionPolicies(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/execution-policies/recompute`);
  return res.data;
}

export async function fetchAutonomousRuns(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/autonomous-runs`);
  return res.data;
}

export async function startAutonomousRuns(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/autonomous-runs/start`);
  return res.data;
}

export async function fetchDistributionPlans(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/distribution-plans`);
  return res.data;
}

export async function recomputeDistributionPlans(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/distribution-plans/recompute`);
  return res.data;
}

export async function fetchMonetizationRoutes(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/monetization-routes`);
  return res.data;
}

export async function recomputeMonetizationRoutes(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/monetization-routes/recompute`);
  return res.data;
}

export async function fetchSuppressionExecutions(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/suppression-executions`);
  return res.data;
}
