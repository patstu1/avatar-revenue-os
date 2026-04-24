import axios from 'axios';

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8001');

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('aro_token') : null;
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options?.headers,
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && typeof window !== 'undefined') {
    localStorage.removeItem('aro_token');
    document.cookie = 'aro_token=; path=/; max-age=0';
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    throw new Error(await res.text());
  }

  if (res.status === 204 || res.headers.get('content-length') === '0') {
    return null as T;
  }

  return res.json();
}

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('aro_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('aro_token');
      document.cookie = 'aro_token=; path=/; max-age=0';
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  login: (email: string, password: string) => api.post('/api/v1/auth/login', { email, password }),
  register: (data: { organization_name: string; email: string; password: string; full_name: string }) => api.post('/api/v1/auth/register', data),
  me: () => api.get('/api/v1/auth/me'),
};

export const brandsApi = {
  list: (page = 1) => api.get('/api/v1/brands/', { params: { page } }),
  get: (id: string) => api.get(`/api/v1/brands/${id}`),
  create: (data: any) => api.post('/api/v1/brands/', data),
  update: (id: string, data: any) => api.patch(`/api/v1/brands/${id}`, data),
};

export const avatarsApi = {
  list: (brandId: string, page = 1) => api.get('/api/v1/avatars/', { params: { brand_id: brandId, page } }),
  get: (id: string) => api.get(`/api/v1/avatars/${id}`),
  create: (data: any) => api.post('/api/v1/avatars/', data),
  update: (id: string, data: any) => api.patch(`/api/v1/avatars/${id}`, data),
  delete: (id: string) => api.delete(`/api/v1/avatars/${id}`),
};

export const offersApi = {
  list: (brandId: string, page = 1) => api.get('/api/v1/offers/', { params: { brand_id: brandId, page } }),
  get: (id: string) => api.get(`/api/v1/offers/${id}`),
  create: (data: any) => api.post('/api/v1/offers/', data),
  delete: (id: string) => api.delete(`/api/v1/offers/${id}`),
};

export const accountsApi = {
  list: (brandId: string, page = 1) => api.get('/api/v1/accounts/', { params: { brand_id: brandId, page } }),
  get: (id: string) => api.get(`/api/v1/accounts/${id}`),
  create: (data: any) => api.post('/api/v1/accounts/', data),
  update: (id: string, data: any) => api.patch(`/api/v1/accounts/${id}`, data),
  delete: (id: string) => api.delete(`/api/v1/accounts/${id}`),
  updateCredentials: (id: string, data: any) => api.put(`/api/v1/accounts/${id}/credentials`, data),
  triggerSync: (id: string) => api.post(`/api/v1/accounts/${id}/sync`),
};

export const providersApi = {
  listAvatarProviders: (avatarId: string) => api.get('/api/v1/providers/avatar', { params: { avatar_id: avatarId } }),
  createAvatarProvider: (data: any) => api.post('/api/v1/providers/avatar', data),
  updateAvatarProvider: (id: string, data: any) => api.patch(`/api/v1/providers/avatar/${id}`, data),
  deleteAvatarProvider: (id: string) => api.delete(`/api/v1/providers/avatar/${id}`),
  listVoiceProviders: (avatarId: string) => api.get('/api/v1/providers/voice', { params: { avatar_id: avatarId } }),
  createVoiceProvider: (data: any) => api.post('/api/v1/providers/voice', data),
  updateVoiceProvider: (id: string, data: any) => api.patch(`/api/v1/providers/voice/${id}`, data),
  deleteVoiceProvider: (id: string) => api.delete(`/api/v1/providers/voice/${id}`),
};

export const dashboardApi = {
  overview: () => api.get('/api/v1/dashboard/overview'),
};

export const settingsApi = {
  getOrganization: () => api.get('/api/v1/settings/organization'),
  updateOrganization: (data: any) => api.patch('/api/v1/settings/organization', data),
  getIntegrations: () => api.get('/api/v1/settings/integrations'),
  saveApiKey: (provider: string, apiKey: string) => api.put(`/api/v1/settings/api-keys/${provider}`, { api_key: apiKey }),
  deleteApiKey: (provider: string) => api.delete(`/api/v1/settings/api-keys/${provider}`),
};

export const decisionsApi = {
  list: (type: string, brandId: string, page = 1) => api.get(`/api/v1/decisions/${type}`, { params: { brand_id: brandId, page } }),
  get: (type: string, id: string) => api.get(`/api/v1/decisions/${type}/${id}`),
};

export const jobsApi = {
  list: (params?: { brand_id?: string; status?: string; page?: number }) => api.get('/api/v1/jobs/', { params }),
  get: (id: string) => api.get(`/api/v1/jobs/${id}`),
  auditLogs: (page = 1) => api.get('/api/v1/jobs/audit/logs', { params: { page } }),
  providerCosts: (brandId?: string) => api.get('/api/v1/jobs/costs/providers', { params: { brand_id: brandId } }),
};

export const healthApi = {
  healthz: () => api.get('/healthz'),
  readyz: () => api.get('/readyz'),
};
