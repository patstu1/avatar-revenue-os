import { api } from './api';

const b = (brandId: string) => `/api/v1/brands/${brandId}`;

export const growthPackApi = {
  growthCommands: (brandId: string) => api.get(`${b(brandId)}/growth-commands`),
  growthCommandsRecompute: (brandId: string) => api.post(`${b(brandId)}/growth-commands/recompute`),
  portfolioLaunchPlan: (brandId: string) => api.get(`${b(brandId)}/portfolio-launch-plan`),
  portfolioLaunchRecompute: (brandId: string) => api.post(`${b(brandId)}/portfolio-launch-plan/recompute`),
  accountBlueprints: (brandId: string) => api.get(`${b(brandId)}/account-launch-blueprints`),
  accountBlueprintsRecompute: (brandId: string) => api.post(`${b(brandId)}/account-launch-blueprints/recompute`),
  blueprint: (id: string) => api.get(`/api/v1/account-launch-blueprints/${id}`),
  platformAllocation: (brandId: string) => api.get(`${b(brandId)}/platform-allocation`),
  platformAllocationRecompute: (brandId: string) => api.post(`${b(brandId)}/platform-allocation/recompute`),
  nicheDeployment: (brandId: string) => api.get(`${b(brandId)}/niche-deployment`),
  nicheDeploymentRecompute: (brandId: string) => api.post(`${b(brandId)}/niche-deployment/recompute`),
  growthBlockers: (brandId: string) => api.get(`${b(brandId)}/growth-blockers`),
  growthBlockersRecompute: (brandId: string) => api.post(`${b(brandId)}/growth-blockers/recompute`),
  capitalDeployment: (brandId: string) => api.get(`${b(brandId)}/capital-deployment`),
  capitalDeploymentRecompute: (brandId: string) => api.post(`${b(brandId)}/capital-deployment/recompute`),
  crossCannibalization: (brandId: string) => api.get(`${b(brandId)}/cross-account-cannibalization`),
  crossCannibalizationRecompute: (brandId: string) => api.post(`${b(brandId)}/cross-account-cannibalization/recompute`),
  portfolioOutput: (brandId: string) => api.get(`${b(brandId)}/portfolio-output`),
  portfolioOutputRecompute: (brandId: string) => api.post(`${b(brandId)}/portfolio-output/recompute`),
};
