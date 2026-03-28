import { api } from './api';

export const analyticsApi = {
  revenueDashboard: (brandId: string) => api.get('/api/v1/analytics/dashboard/revenue', { params: { brand_id: brandId } }),
  contentPerformance: (brandId: string) => api.get('/api/v1/analytics/dashboard/content-performance', { params: { brand_id: brandId } }),
  funnelDashboard: (brandId: string) => api.get('/api/v1/analytics/dashboard/funnel', { params: { brand_id: brandId } }),
  revenueLeaks: (brandId: string) => api.get('/api/v1/analytics/dashboard/leaks', { params: { brand_id: brandId } }),
  bottlenecks: (brandId: string) => api.get('/api/v1/analytics/dashboard/bottlenecks', { params: { brand_id: brandId } }),
  detectWinners: (brandId: string) => api.post(`/api/v1/analytics/winners/detect?brand_id=${brandId}`),
  evaluateSuppressions: (brandId: string) => api.post(`/api/v1/analytics/suppressions/evaluate?brand_id=${brandId}`),
  trackClick: (data: any) => api.post('/api/v1/analytics/events/track-click', data),
  trackConversion: (data: any) => api.post('/api/v1/analytics/events/track-conversion', data),
};
