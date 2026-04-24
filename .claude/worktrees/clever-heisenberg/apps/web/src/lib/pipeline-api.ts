import { api } from './api';

export const pipelineApi = {
  listBriefs: (brandId: string) => api.get('/api/v1/pipeline/briefs', { params: { brand_id: brandId } }),
  getBrief: (id: string) => api.get(`/api/v1/pipeline/briefs/${id}`),
  updateBrief: (id: string, data: any) => api.patch(`/api/v1/pipeline/briefs/${id}`, data),
  generateScript: (briefId: string) => api.post(`/api/v1/pipeline/briefs/${briefId}/generate-scripts`),

  listScripts: (brandId: string) => api.get('/api/v1/pipeline/scripts', { params: { brand_id: brandId } }),
  getScript: (id: string) => api.get(`/api/v1/pipeline/scripts/${id}`),
  updateScript: (id: string, data: any) => api.patch(`/api/v1/pipeline/scripts/${id}`, data),
  scoreScript: (id: string) => api.post(`/api/v1/pipeline/scripts/${id}/score`),
  generateMedia: (scriptId: string) => api.post(`/api/v1/pipeline/scripts/${scriptId}/generate-media`),

  listMediaJobs: (brandId: string) => api.get('/api/v1/pipeline/media-jobs', { params: { brand_id: brandId } }),
  getMediaJob: (id: string) => api.get(`/api/v1/pipeline/media-jobs/${id}`),

  contentLibrary: (brandId: string, status?: string) =>
    api.get('/api/v1/pipeline/content/library', { params: { brand_id: brandId, status } }),
  runQA: (contentId: string) => api.post(`/api/v1/pipeline/content/${contentId}/run-qa`),
  getQA: (contentId: string) => api.get(`/api/v1/pipeline/qa/${contentId}`),
  approve: (contentId: string, notes = '') => api.post(`/api/v1/pipeline/content/${contentId}/approve`, { notes }),
  reject: (contentId: string, notes = '') => api.post(`/api/v1/pipeline/content/${contentId}/reject`, { notes }),
  requestChanges: (contentId: string, notes = '') => api.post(`/api/v1/pipeline/content/${contentId}/request-changes`, { notes }),
  schedule: (contentId: string, data: any) => api.post(`/api/v1/pipeline/content/${contentId}/schedule`, data),
  publishNow: (contentId: string, data: any) => api.post(`/api/v1/pipeline/content/${contentId}/publish-now`, data),
  publishStatus: (contentId: string) => api.get(`/api/v1/pipeline/content/${contentId}/publish-status`),
  approvalQueue: (brandId: string) => api.get('/api/v1/pipeline/approvals/queue', { params: { brand_id: brandId } }),
};
