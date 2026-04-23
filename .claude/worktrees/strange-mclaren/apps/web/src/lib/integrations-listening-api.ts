import { api } from './api';

export const integrationsListeningApi = {
  connectors: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/integrations/connectors`),
  listening: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/integrations/listening`),
  competitorSignals: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/integrations/competitor-signals`),
  clusters: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/integrations/clusters`),
  blockers: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/integrations/blockers`),
  recompute: (org_id: string) =>
    api.post(`/api/v1/orgs/${org_id}/integrations/recompute`),
};
