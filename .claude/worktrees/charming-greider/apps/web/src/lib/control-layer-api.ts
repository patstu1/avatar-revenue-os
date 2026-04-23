/**
 * Control Layer API — the operator's primary command surface.
 *
 * This replaces fragmented dashboard API calls with a unified
 * operational API that surfaces real system state, pending actions,
 * and recent events in one coordinated interface.
 */
import { api } from './api';

export const controlLayerApi = {
  /** Complete control layer state in one call */
  dashboard: () => api.get('/api/v1/control-layer/dashboard'),

  /** Real-time system health */
  health: () => api.get('/api/v1/control-layer/health'),

  /** Pending operator actions */
  actions: (params?: { category?: string; priority?: string; limit?: number }) =>
    api.get('/api/v1/control-layer/actions', { params }),

  /** Complete an operator action */
  completeAction: (actionId: string, result: Record<string, unknown> = {}) =>
    api.post(`/api/v1/control-layer/actions/${actionId}/complete`, { result }),

  /** Dismiss an operator action */
  dismissAction: (actionId: string, reason?: string) =>
    api.post(`/api/v1/control-layer/actions/${actionId}/dismiss`, { reason }),

  /** System events feed */
  events: (params?: { domain?: string; severity?: string; limit?: number }) =>
    api.get('/api/v1/control-layer/events', { params }),
};
