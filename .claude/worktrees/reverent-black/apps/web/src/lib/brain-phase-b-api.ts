import { api } from './api';

export async function fetchBrainDecisions(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/brain-decisions`);
  return res.data;
}

export async function recomputeBrainDecisions(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/brain-decisions/recompute`);
  return res.data;
}

export async function fetchPolicyEvaluations(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/policy-evaluations`);
  return res.data;
}

export async function fetchConfidenceReports(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/confidence-reports`);
  return res.data;
}

export async function fetchUpsideCostEstimates(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/upside-cost-estimates`);
  return res.data;
}

export async function fetchArbitrationReports(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/arbitration-reports`);
  return res.data;
}
