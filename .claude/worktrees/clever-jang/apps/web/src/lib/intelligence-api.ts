/**
 * Intelligence Hub API — unified intelligence surface.
 */
import { api } from './api';

export const intelligenceApi = {
  /** Full intelligence summary */
  summary: (brandId?: string) =>
    api.get('/api/v1/intelligence/summary', { params: brandId ? { brand_id: brandId } : {} }),

  /** Generation context (patterns, suppressions, rules) */
  generationContext: (brandId: string, platform?: string) =>
    api.get('/api/v1/intelligence/generation-context', {
      params: { brand_id: brandId, ...(platform ? { platform } : {}) },
    }),

  /** Kill ledger check */
  killCheck: (brandId: string, entityType?: string) =>
    api.get('/api/v1/intelligence/kill-check', {
      params: { brand_id: brandId, ...(entityType ? { entity_type: entityType } : {}) },
    }),

  /** Surface intelligence as operator actions */
  surfaceActions: (brandId: string) =>
    api.post('/api/v1/intelligence/surface-actions', null, { params: { brand_id: brandId } }),
};
