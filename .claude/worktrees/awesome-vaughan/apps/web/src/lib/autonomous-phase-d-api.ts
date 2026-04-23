import { api } from './api';

export async function fetchAgentRuns(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/agent-runs`);
  return res.data;
}

export async function fetchRevenuePressure(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/revenue-pressure`);
  return res.data;
}

export async function recomputeRevenuePressure(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/revenue-pressure/recompute`);
  return res.data;
}

export async function fetchOverridePolicies(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/override-policies`);
  return res.data;
}

export async function recomputeOverridePolicies(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/override-policies/recompute`);
  return res.data;
}

export async function fetchBlockerDetection(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/blocker-detection`);
  return res.data;
}

export async function recomputeBlockerDetection(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/blocker-detection/recompute`);
  return res.data;
}

export async function fetchOperatorEscalations(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/operator-escalations`);
  return res.data;
}
