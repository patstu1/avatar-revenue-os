/**
 * Monetization Hub API — revenue operations surface.
 */
import { api } from './api';

export const monetizationHubApi = {
  /** Brand revenue state (30d revenue, offers, monetization rate) */
  revenueState: (brandId: string) =>
    api.get('/api/v1/monetization-hub/revenue-state', { params: { brand_id: brandId } }),

  /** Content items with their assigned offers */
  contentOffers: (brandId: string, limit = 50) =>
    api.get('/api/v1/monetization-hub/content-offers', { params: { brand_id: brandId, limit } }),

  /** Assign an offer to content */
  assignOffer: (contentId: string, offerId: string) =>
    api.post('/api/v1/monetization-hub/assign-offer', null, {
      params: { content_id: contentId, offer_id: offerId },
    }),

  /** Manually attribute a revenue event */
  attributeRevenue: (brandId: string, revenue: number, opts?: {
    event_type?: string; source?: string; offer_id?: string; content_item_id?: string;
  }) =>
    api.post('/api/v1/monetization-hub/attribute-revenue', null, {
      params: { brand_id: brandId, revenue, ...opts },
    }),

  /** Surface monetization actions for control layer */
  surfaceActions: (brandId: string) =>
    api.post('/api/v1/monetization-hub/surface-actions', null, { params: { brand_id: brandId } }),
};
