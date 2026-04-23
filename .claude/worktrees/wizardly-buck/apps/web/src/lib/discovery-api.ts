import { api } from './api';

export const discoveryApi = {
  ingestSignals: (brandId: string, data: any) =>
    api.post(`/api/v1/brands/${brandId}/signals/ingest`, data),
  getSignals: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/signals`),
  getNiches: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/niches`),
  recomputeNiches: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/niches/recompute`),
  getOpportunities: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/opportunities`),
  recomputeOpportunities: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/opportunities/recompute`),
  getQueue: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/opportunities/queue`),
  forecast: (brandId: string, topicId: string) =>
    api.post(`/api/v1/brands/${brandId}/opportunities/${topicId}/forecast`),
  offerFit: (brandId: string, topicId: string) =>
    api.post(`/api/v1/brands/${brandId}/opportunities/${topicId}/offer-fit`),
  triggerBrief: (brandId: string, topicId: string) =>
    api.post(`/api/v1/brands/${brandId}/opportunities/${topicId}/trigger-brief`),
  getTrends: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/trends`),
  recomputeTrends: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/trends/recompute`),
  getSaturation: (brandId: string, recompute = false) =>
    api.get(`/api/v1/brands/${brandId}/saturation`, { params: { recompute } }),
  getForecasts: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/profit-forecasts`),
  getRecommendations: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/recommendations`),
};
