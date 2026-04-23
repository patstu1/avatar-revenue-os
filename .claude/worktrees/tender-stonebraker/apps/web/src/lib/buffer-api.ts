import { api } from './api';

export async function fetchBufferProfiles(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/buffer-profiles`);
  return res.data;
}

export async function createBufferProfile(brandId: string, data: Record<string, unknown>, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/buffer-profiles`, data);
  return res.data;
}

export async function updateBufferProfile(profileId: string, data: Record<string, unknown>, _token: string) {
  const res = await api.patch(`/api/v1/buffer-profiles/${profileId}`, data);
  return res.data;
}

export async function fetchBufferPublishJobs(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/buffer-publish-jobs`);
  return res.data;
}

export async function recomputeBufferPublishJobs(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/buffer-publish-jobs/recompute`);
  return res.data;
}

export async function submitBufferJob(jobId: string, _token: string) {
  const res = await api.post(`/api/v1/buffer-publish-jobs/${jobId}/submit`);
  return res.data;
}

export async function recomputeBufferStatusSync(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/buffer-status-sync/recompute`);
  return res.data;
}

export async function fetchBufferBlockers(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/buffer-blockers`);
  return res.data;
}
