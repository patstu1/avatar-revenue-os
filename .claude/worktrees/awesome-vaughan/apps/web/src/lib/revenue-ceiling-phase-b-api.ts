import { api } from './api';

export const revenueCeilingPhaseBApi = {
  highTicketOpportunities: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/high-ticket-opportunities`),
  recomputeHighTicket: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/high-ticket-opportunities/recompute`),
  productOpportunities: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/product-opportunities`),
  recomputeProductOpportunities: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/product-opportunities/recompute`),
  revenueDensity: (brandId: string) => api.get(`/api/v1/brands/${brandId}/revenue-density`),
  recomputeRevenueDensity: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/revenue-density/recompute`),
  upsellRecommendations: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/upsell-recommendations`),
  recomputeUpsell: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/upsell-recommendations/recompute`),
};
