const API = process.env.NEXT_PUBLIC_API_URL ?? (typeof window !== "undefined" ? window.location.origin : "http://localhost:8001");

function authHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("aro_token") : null;
  return { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

async function apiFetch(path: string, opts?: RequestInit) {
  const res = await fetch(`${API}${path}`, {
    headers: { ...authHeaders(), ...(opts?.headers as Record<string, string>) },
    ...opts,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface ActiveExperiment { id: string; experiment_name: string; hypothesis: string; tested_variable: string; target_platform: string | null; primary_metric: string; status: string; explanation: string | null; }
export interface PWWinner { id: string; win_margin: number; confidence: number; sample_size: number; promoted: boolean; explanation: string | null; }
export interface PWLoser { id: string; loss_margin: number; suppressed: boolean; explanation: string | null; }
export interface PromotedRule { id: string; rule_type: string; rule_key: string; rule_value: any; target_platform: string | null; weight_boost: number; is_active: boolean; explanation: string | null; }

export const fetchExperiments = (brandId: string): Promise<ActiveExperiment[]> => apiFetch(`/api/v1/brands/${brandId}/experiments`);
export const fetchWinners = (brandId: string): Promise<PWWinner[]> => apiFetch(`/api/v1/brands/${brandId}/experiment-winners`);
export const fetchLosers = (brandId: string): Promise<PWLoser[]> => apiFetch(`/api/v1/brands/${brandId}/experiment-losers`);
export const fetchPromotedRules = (brandId: string): Promise<PromotedRule[]> => apiFetch(`/api/v1/brands/${brandId}/promoted-rules`);
