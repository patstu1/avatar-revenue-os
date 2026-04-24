import { api } from './api';

export const integrationsDashboardApi = {
  listProviders: () =>
    api.get(`/api/v1/integrations/providers`),
  configure: () =>
    api.post(`/api/v1/integrations/configure`),
  testConnection: () =>
    api.post(`/api/v1/integrations/test`),
  seedProviders: () =>
    api.post(`/api/v1/integrations/seed`),
  setCredential: (provider_key: string) =>
    api.post(`/api/v1/integrations/providers/${provider_key}/credential`),
  getRoute: () =>
    api.get(`/api/v1/integrations/route`),
  enableProvider: (provider_key: string) =>
    api.post(`/api/v1/integrations/providers/${provider_key}/enable`),
  disableProvider: (provider_key: string) =>
    api.post(`/api/v1/integrations/providers/${provider_key}/disable`),
};
