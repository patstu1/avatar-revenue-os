import { api } from './api';

export async function fetchBrainMemory(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/brain-memory`);
  return res.data;
}

export async function recomputeBrainMemory(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/brain-memory/recompute`);
  return res.data;
}

export async function fetchAccountStates(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/account-states`);
  return res.data;
}

export async function recomputeAccountStates(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/account-states/recompute`);
  return res.data;
}

export async function fetchOpportunityStates(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/opportunity-states`);
  return res.data;
}

export async function recomputeOpportunityStates(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/opportunity-states/recompute`);
  return res.data;
}

export async function fetchExecutionStates(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/execution-states`);
  return res.data;
}

export async function recomputeExecutionStates(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/execution-states/recompute`);
  return res.data;
}

export async function fetchAudienceStatesV2(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/audience-states-v2`);
  return res.data;
}

export async function recomputeAudienceStatesV2(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/audience-states-v2/recompute`);
  return res.data;
}
