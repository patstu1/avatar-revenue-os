import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('aro_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('aro_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  login: (email: string, password: string) =>
    api.post('/api/v1/auth/login', { email, password }),
  register: (data: { organization_name: string; email: string; password: string; full_name: string }) =>
    api.post('/api/v1/auth/register', data),
  me: () => api.get('/api/v1/auth/me'),
};

export const brandsApi = {
  list: (page = 1) => api.get('/api/v1/brands', { params: { page } }),
  get: (id: string) => api.get(`/api/v1/brands/${id}`),
  create: (data: any) => api.post('/api/v1/brands', data),
};

export const avatarsApi = {
  list: (brandId: string, page = 1) => api.get('/api/v1/avatars', { params: { brand_id: brandId, page } }),
  get: (id: string) => api.get(`/api/v1/avatars/${id}`),
  create: (data: any) => api.post('/api/v1/avatars', data),
};

export const offersApi = {
  list: (brandId: string, page = 1) => api.get('/api/v1/offers', { params: { brand_id: brandId, page } }),
  get: (id: string) => api.get(`/api/v1/offers/${id}`),
  create: (data: any) => api.post('/api/v1/offers', data),
};

export const accountsApi = {
  list: (brandId: string, page = 1) => api.get('/api/v1/accounts', { params: { brand_id: brandId, page } }),
  get: (id: string) => api.get(`/api/v1/accounts/${id}`),
  create: (data: any) => api.post('/api/v1/accounts', data),
};

export const decisionsApi = {
  list: (type: string, brandId: string, page = 1) =>
    api.get(`/api/v1/decisions/${type}`, { params: { brand_id: brandId, page } }),
  get: (type: string, id: string) => api.get(`/api/v1/decisions/${type}/${id}`),
};

export const jobsApi = {
  list: (params?: { brand_id?: string; status?: string; page?: number }) =>
    api.get('/api/v1/jobs', { params }),
  get: (id: string) => api.get(`/api/v1/jobs/${id}`),
  auditLogs: (page = 1) => api.get('/api/v1/jobs/audit/logs', { params: { page } }),
  providerCosts: (brandId?: string) => api.get('/api/v1/jobs/costs/providers', { params: { brand_id: brandId } }),
};

export const healthApi = {
  healthz: () => api.get('/healthz'),
  readyz: () => api.get('/readyz'),
};
