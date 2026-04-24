import { api } from './api';

export const recoveryEngineApi = {
  incidents: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/recovery/incidents`),
  recompute: (org_id: string) =>
    api.post(`/api/v1/orgs/${org_id}/recovery/recompute`),
  rollbacks: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/recovery/rollbacks`),
  reroutes: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/recovery/reroutes`),
  throttles: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/recovery/throttles`),
  outcomes: (org_id: string) =>
    api.get(`/api/v1/orgs/${org_id}/recovery/outcomes`),
};
