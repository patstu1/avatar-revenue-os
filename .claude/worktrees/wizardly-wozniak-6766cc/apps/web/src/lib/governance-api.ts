/**
 * Governance Hub API — approvals, permissions, memory surface.
 */
import { api } from './api';

export const governanceApi = {
  /** Governance state: approvals, workflows, permissions, gatekeeper, memory */
  summary: () => api.get('/api/v1/governance/summary'),

  /** Memory entries for decision context */
  memory: (brandId: string, memoryType?: string, limit = 20) =>
    api.get('/api/v1/governance/memory', {
      params: { brand_id: brandId, ...(memoryType ? { memory_type: memoryType } : {}), limit },
    }),

  /** Creative memory atoms */
  creativeAtoms: (brandId: string, atomType?: string, limit = 20) =>
    api.get('/api/v1/governance/creative-atoms', {
      params: { brand_id: brandId, ...(atomType ? { atom_type: atomType } : {}), limit },
    }),

  /** Check permission for an action */
  checkPermission: (actionClass: string) =>
    api.post('/api/v1/governance/check-permission', null, { params: { action_class: actionClass } }),

  /** Record generation outcome for memory */
  recordOutcome: (brandId: string, contentItemId: string, qualityScore?: number, approvalStatus?: string) =>
    api.post('/api/v1/governance/record-outcome', null, {
      params: { brand_id: brandId, content_item_id: contentItemId, quality_score: qualityScore, approval_status: approvalStatus },
    }),

  /** Surface governance actions */
  surfaceActions: () => api.post('/api/v1/governance/surface-actions'),
};
