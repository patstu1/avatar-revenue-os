import { api } from './api';

export const phase7Api = {
  recompute: (brandId: string) => api.post(`/api/v1/brands/${brandId}/phase7/recompute`),
  sponsorOpportunities: (brandId: string) => api.get(`/api/v1/brands/${brandId}/sponsor-opportunities`),
  commentCashSignals: (brandId: string) => api.get(`/api/v1/brands/${brandId}/comment-cash-signals`),
  roadmap: (brandId: string) => api.get(`/api/v1/brands/${brandId}/roadmap`),
  capitalAllocation: (brandId: string) => api.get(`/api/v1/brands/${brandId}/capital-allocation`),
  knowledgeGraph: (brandId: string) => api.get(`/api/v1/brands/${brandId}/knowledge-graph`),
  operatorCockpit: (brandId: string) => api.get(`/api/v1/brands/${brandId}/operator-cockpit`),
};
