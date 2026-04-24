import { api } from './api';

export async function fetchAgentRegistry(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/agent-registry`);
  return res.data;
}

export async function fetchAgentRunsV2(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/agent-runs-v2`);
  return res.data;
}

export async function recomputeAgentMesh(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/agent-mesh/recompute`);
  return res.data;
}

export async function fetchWorkflowCoordination(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/workflow-coordination`);
  return res.data;
}

export async function fetchSharedContextEvents(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/shared-context-events`);
  return res.data;
}
