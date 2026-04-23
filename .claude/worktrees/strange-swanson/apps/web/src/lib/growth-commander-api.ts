import { api } from './api';

export const growthCommanderApi = {
  recompute: (brandId: string) => api.post(`/api/v1/brands/${brandId}/growth-commands/recompute`),
  commands: (brandId: string) => api.get(`/api/v1/brands/${brandId}/growth-commands`),
  runs: (brandId: string) => api.get(`/api/v1/brands/${brandId}/growth-command-runs`),
  portfolioAssessment: (brandId: string) => api.get(`/api/v1/brands/${brandId}/portfolio-assessment`),
};
