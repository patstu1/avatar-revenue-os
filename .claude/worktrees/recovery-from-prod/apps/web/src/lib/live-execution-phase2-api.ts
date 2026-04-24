import { api } from './api';

export const lec2Api = {
  webhookEvents: (brandId: string) => api.get(`/api/v1/brands/${brandId}/webhook-events`),
  ingestWebhook: (brandId: string, data: any) =>
    api.post(`/api/v1/brands/${brandId}/webhook-events`, data),
  eventIngestions: (brandId: string) => api.get(`/api/v1/brands/${brandId}/event-ingestions`),
  recomputeIngestions: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/event-ingestions/recompute`),
  sequenceTriggers: (brandId: string) => api.get(`/api/v1/brands/${brandId}/sequence-triggers`),
  processSequenceTriggers: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/sequence-triggers/process`),
  paymentSyncs: (brandId: string) => api.get(`/api/v1/brands/${brandId}/payment-syncs`),
  runPaymentSync: (brandId: string) => api.post(`/api/v1/brands/${brandId}/payment-syncs/run`),
  analyticsSyncs: (brandId: string) => api.get(`/api/v1/brands/${brandId}/analytics-syncs`),
  runAnalyticsSync: (brandId: string) => api.post(`/api/v1/brands/${brandId}/analytics-syncs/run`),
  adImports: (brandId: string) => api.get(`/api/v1/brands/${brandId}/ad-imports`),
  runAdImport: (brandId: string) => api.post(`/api/v1/brands/${brandId}/ad-imports/run`),
  bufferExecutionTruth: (brandId: string) => api.get(`/api/v1/brands/${brandId}/buffer-execution-truth`),
  recomputeBufferTruth: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/buffer-execution-truth/recompute`),
  bufferRetries: (brandId: string) => api.get(`/api/v1/brands/${brandId}/buffer-retries`),
  recomputeBufferRetries: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/buffer-retries/recompute`),
  bufferCapabilities: (brandId: string) => api.get(`/api/v1/brands/${brandId}/buffer-capabilities`),
  recomputeBufferCapabilities: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/buffer-capabilities/recompute`),
};
