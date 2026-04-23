/**
 * Orchestration Hub API — jobs, workers, providers surface.
 */
import { api } from './api';

export const orchestrationApi = {
  /** Full orchestration state (jobs, queues, throughput, failures) */
  state: () => api.get('/api/v1/orchestration/state'),

  /** Provider health (healthy/degraded/blocked) */
  providers: (brandId?: string) =>
    api.get('/api/v1/orchestration/providers', { params: brandId ? { brand_id: brandId } : {} }),

  /** Check if a specific provider is ready */
  providerCheck: (providerKey: string, brandId?: string) =>
    api.get('/api/v1/orchestration/provider-check', {
      params: { provider_key: providerKey, ...(brandId ? { brand_id: brandId } : {}) },
    }),

  /** Surface orchestration actions (stuck jobs, provider blockers) */
  surfaceActions: () => api.post('/api/v1/orchestration/surface-actions'),
};
