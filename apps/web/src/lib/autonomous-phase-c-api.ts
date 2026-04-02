import { api } from './api';

export async function fetchFunnelExecution(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/funnel-execution`);
  return res.data;
}

export async function recomputeFunnelExecution(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/funnel-execution/recompute`);
  return res.data;
}

export async function fetchPaidOperator(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/paid-operator`);
  return res.data;
}

export async function recomputePaidOperator(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/paid-operator/recompute`);
  return res.data;
}

export async function fetchSponsorAutonomy(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/sponsor-autonomy`);
  return res.data;
}

export async function recomputeSponsorAutonomy(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/sponsor-autonomy/recompute`);
  return res.data;
}

export async function fetchRetentionAutonomy(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/retention-autonomy`);
  return res.data;
}

export async function recomputeRetentionAutonomy(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/retention-autonomy/recompute`);
  return res.data;
}

export async function fetchRecoveryAutonomy(brandId: string, _token: string) {
  const res = await api.get(`/api/v1/brands/${brandId}/recovery-autonomy`);
  return res.data;
}

export async function recomputeRecoveryAutonomy(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/recovery-autonomy/recompute`);
  return res.data;
}

export async function advanceActionStatus(
  brandId: string,
  module: string,
  recordId: string,
  targetStatus: string,
  operatorNotes?: string,
) {
  const res = await api.patch(
    `/api/v1/brands/${brandId}/phase-c/${module}/${recordId}/status`,
    { target_status: targetStatus, operator_notes: operatorNotes },
  );
  return res.data;
}

export async function ingestPaidPerformance(
  brandId: string,
  runId: string,
  metrics: { cpa_actual: number; cpa_target?: number; spend_7d: number; conversions_7d: number; roi_actual: number },
) {
  const res = await api.post(
    `/api/v1/brands/${brandId}/paid-operator/${runId}/performance`,
    metrics,
  );
  return res.data;
}

export async function batchExecuteApproved(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/phase-c/execute-approved`);
  return res.data;
}

export async function notifyOperator(brandId: string, _token: string) {
  const res = await api.post(`/api/v1/brands/${brandId}/phase-c/notify-operator`);
  return res.data;
}
