import { api } from './api';

export const gmApi = {
  getMachineState: () => api.get('/api/v1/gm/machine-state'),
  listSessions: () => api.get('/api/v1/gm/sessions'),
  createSession: (title = 'GM Strategy Session') =>
    api.post('/api/v1/gm/sessions', { title }),
  getMessages: (sessionId: string) =>
    api.get(`/api/v1/gm/sessions/${sessionId}/messages`),
  sendMessage: (sessionId: string, content: string) =>
    api.post(`/api/v1/gm/sessions/${sessionId}/messages`, { content }),
  getBlueprint: () => api.get('/api/v1/gm/blueprint'),
  approveBlueprint: () => api.post('/api/v1/gm/blueprint/approve'),
  executeStep: (stepKey: string) =>
    api.post(`/api/v1/gm/blueprint/execute/${stepKey}`),
};
