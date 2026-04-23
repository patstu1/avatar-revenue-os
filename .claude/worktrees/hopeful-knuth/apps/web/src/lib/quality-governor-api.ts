import { api } from './api';

export const qualityGovernorApi = {
  reports: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/quality-governor`),
  recompute: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/quality-governor/recompute`),
  scoreItem: (brandId: string, content_item_id: string) =>
    api.post(`/api/v1/brands/${brandId}/quality-governor/${content_item_id}/score`),
  blocks: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/quality-governor/blocks`),
};
