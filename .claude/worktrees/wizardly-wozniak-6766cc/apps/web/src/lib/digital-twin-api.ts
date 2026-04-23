import { api } from './api';

export const digitalTwinApi = {
  runs: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/simulations`),
  runSimulation: (brandId: string) =>
    api.post(`/api/v1/brands/${brandId}/simulations/run`),
  scenarios: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/simulations/scenarios`),
  recommendations: (brandId: string) =>
    api.get(`/api/v1/brands/${brandId}/simulations/recommendations`),
};
