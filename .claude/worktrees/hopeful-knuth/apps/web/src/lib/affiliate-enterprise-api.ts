import { api } from './api';

export const affiliateEnterpriseApi = {
  governanceRules: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/affiliate/governance-rules`),
  banned: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/affiliate/banned`),
  approvals: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/affiliate/approvals`),
  riskFlags: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/affiliate/risk-flags`),
  partners: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/affiliate/partners`),
  recomputeGovernance: (org_id: string) =>
    api.post(`/api/v1/orgs/${org_id}/affiliate/governance/recompute`),
  recomputePartners: (org_id: string) =>
    api.post(`/api/v1/orgs/${org_id}/affiliate/partners/recompute`),
};
