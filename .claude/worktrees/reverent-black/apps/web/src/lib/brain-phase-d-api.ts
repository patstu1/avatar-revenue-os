import { api } from './api';

export async function fetchMetaMonitoring(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/meta-monitoring`);
  return res.data;
}

export async function recomputeMetaMonitoring(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/meta-monitoring/recompute`);
  return res.data;
}

export async function fetchSelfCorrections(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/self-corrections`);
  return res.data;
}

export async function fetchReadinessBrain(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/readiness-brain`);
  return res.data;
}

export async function recomputeReadinessBrain(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/readiness-brain/recompute`);
  return res.data;
}

export async function fetchBrainEscalations(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/brain-escalations`);
  return res.data;
}
