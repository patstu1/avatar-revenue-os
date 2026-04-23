import { api } from './api';

export const gatekeeperApi = {
  completion: (brandId: string) => api.get(`/api/v1/brands/${brandId}/gatekeeper/completion`),
  recomputeCompletion: (brandId: string) => api.post(`/api/v1/brands/${brandId}/gatekeeper/completion/recompute`),
  truth: (brandId: string) => api.get(`/api/v1/brands/${brandId}/gatekeeper/truth`),
  recomputeTruth: (brandId: string) => api.post(`/api/v1/brands/${brandId}/gatekeeper/truth/recompute`),
  executionClosure: (brandId: string) => api.get(`/api/v1/brands/${brandId}/gatekeeper/execution-closure`),
  recomputeExecutionClosure: (brandId: string) => api.post(`/api/v1/brands/${brandId}/gatekeeper/execution-closure/recompute`),
  tests: (brandId: string) => api.get(`/api/v1/brands/${brandId}/gatekeeper/tests`),
  recomputeTests: (brandId: string) => api.post(`/api/v1/brands/${brandId}/gatekeeper/tests/recompute`),
  dependencies: (brandId: string) => api.get(`/api/v1/brands/${brandId}/gatekeeper/dependencies`),
  recomputeDependencies: (brandId: string) => api.post(`/api/v1/brands/${brandId}/gatekeeper/dependencies/recompute`),
  contradictions: (brandId: string) => api.get(`/api/v1/brands/${brandId}/gatekeeper/contradictions`),
  recomputeContradictions: (brandId: string) => api.post(`/api/v1/brands/${brandId}/gatekeeper/contradictions/recompute`),
  operatorCommands: (brandId: string) => api.get(`/api/v1/brands/${brandId}/gatekeeper/operator-commands`),
  recomputeOperatorCommands: (brandId: string) => api.post(`/api/v1/brands/${brandId}/gatekeeper/operator-commands/recompute`),
  expansionPermissions: (brandId: string) => api.get(`/api/v1/brands/${brandId}/gatekeeper/expansion-permissions`),
  recomputeExpansionPermissions: (brandId: string) => api.post(`/api/v1/brands/${brandId}/gatekeeper/expansion-permissions/recompute`),
  alerts: (brandId: string) => api.get(`/api/v1/brands/${brandId}/gatekeeper/alerts`),
  auditLedger: (brandId: string) => api.get(`/api/v1/brands/${brandId}/gatekeeper/audit-ledger`),
};
