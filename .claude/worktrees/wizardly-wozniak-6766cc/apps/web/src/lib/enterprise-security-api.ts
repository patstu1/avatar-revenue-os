import { api } from './api';

export const enterpriseSecurityApi = {
  roles: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/security/roles`),
  seedRoles: (org_id: string) =>
    api.post(`/api/v1/orgs/${org_id}/security/seed-roles`),
  auditTrail: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/security/audit-trail`),
  dataPolicies: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/security/data-policies`),
  compliance: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/security/compliance`),
  recomputeCompliance: (org_id: string) =>
    api.post(`/api/v1/orgs/${org_id}/security/compliance/recompute`),
  modelIsolation: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/security/model-isolation`),
  riskOverrides: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/security/risk-overrides`),
};
