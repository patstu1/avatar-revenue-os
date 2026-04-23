import { api } from './api';

export const landingPagesApi = {
  list: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/landing-pages`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/landing-pages/recompute`),
  variants: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/landing-page-variants`),
  quality: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/landing-page-quality`),
  publish: (brandId: string, page_id: string) =>
    api.post(`/api/v1/brands/${brandId}/landing-pages/${page_id}/publish`),
};
