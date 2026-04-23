import { api } from './api';

export const copilotApi = {
  listSessions: (brandId: string) => api.get(`/api/v1/brands/${brandId}/copilot/sessions`),
  createSession: (brandId: string, title: string = 'Operator session') => api.post(`/api/v1/brands/${brandId}/copilot/sessions`, { title }),
  getMessages: (sessionId: string) => api.get(`/api/v1/copilot/sessions/${sessionId}/messages`),
  sendMessage: (sessionId: string, content: string, quick_prompt_key?: string) => api.post(`/api/v1/copilot/sessions/${sessionId}/messages`, { content, quick_prompt_key }),
  quickStatus: (brandId: string) => api.get(`/api/v1/brands/${brandId}/copilot/quick-status`),
  operatorActions: (brandId: string) => api.get(`/api/v1/brands/${brandId}/copilot/operator-actions`),
  missingItems: (brandId: string) => api.get(`/api/v1/brands/${brandId}/copilot/missing-items`),
  providers: (brandId: string) => api.get(`/api/v1/brands/${brandId}/copilot/providers`),
  providerReadiness: (brandId: string) => api.get(`/api/v1/brands/${brandId}/copilot/provider-readiness`),
};
