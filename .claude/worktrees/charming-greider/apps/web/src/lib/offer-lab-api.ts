import { api } from './api';

export const offerLabApi = {
  offers: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/offer-lab/offers`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/offer-lab/offers/recompute`),
  variants: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/offer-lab/variants`),
  bundles: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/offer-lab/bundles`),
  blockers: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/offer-lab/blockers`),
  learning: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/offer-lab/learning`),
};
