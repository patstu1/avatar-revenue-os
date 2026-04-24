import { api } from './api';

export async function fetchSignalScans(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/signal-scans`);
  return res.data;
}

export async function recomputeSignalScans(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/signal-scans/recompute`);
  return res.data;
}

export async function fetchAutoQueue(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/auto-queue`);
  return res.data;
}

export async function rebuildAutoQueue(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/auto-queue/rebuild`);
  return res.data;
}

export async function fetchAccountWarmup(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/account-warmup`);
  return res.data;
}

export async function recomputeAccountWarmup(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/account-warmup/recompute`);
  return res.data;
}

export async function fetchAccountOutput(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/account-output`);
  return res.data;
}

export async function recomputeAccountOutput(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/account-output/recompute`);
  return res.data;
}

export async function fetchAccountMaturity(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/account-maturity`);
  return res.data;
}

export async function fetchPlatformWarmupPolicies(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/platform-warmup-policies`);
  return res.data;
}
