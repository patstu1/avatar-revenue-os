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

export interface WinningPattern {
  id: string;
  pattern_type: string;
  pattern_name: string;
  platform: string | null;
  niche: string | null;
  content_form: string | null;
  monetization_method: string | null;
  performance_band: string;
  confidence: number;
  win_score: number;
  decay_score: number;
  usage_count: number;
  explanation: string | null;
}

export interface PatternCluster {
  id: string;
  cluster_name: string;
  cluster_type: string;
  platform: string | null;
  avg_win_score: number;
  pattern_count: number;
  explanation: string | null;
}

export interface LosingPattern {
  id: string;
  pattern_type: string;
  pattern_name: string;
  platform: string | null;
  fail_score: number;
  suppress_reason: string | null;
}

export interface PatternReuse {
  id: string;
  target_platform: string;
  target_content_form: string | null;
  expected_uplift: number;
  confidence: number;
  explanation: string | null;
}

export interface PatternDecay {
  id: string;
  decay_rate: number;
  decay_reason: string;
  previous_win_score: number;
  current_win_score: number;
  recommendation: string | null;
}

export function fetchPatterns(brandId: string): Promise<WinningPattern[]> {
  return apiFetch(`/api/v1/brands/${brandId}/pattern-memory`);
}

export function recomputePatterns(brandId: string) {
  return apiFetch(`/api/v1/brands/${brandId}/pattern-memory/recompute`, { method: "POST" });
}

export function fetchClusters(brandId: string): Promise<PatternCluster[]> {
  return apiFetch(`/api/v1/brands/${brandId}/pattern-clusters`);
}

export function fetchLosers(brandId: string): Promise<LosingPattern[]> {
  return apiFetch(`/api/v1/brands/${brandId}/losing-patterns`);
}

export function fetchReuse(brandId: string): Promise<PatternReuse[]> {
  return apiFetch(`/api/v1/brands/${brandId}/pattern-reuse`);
}

export function fetchDecay(brandId: string): Promise<PatternDecay[]> {
  return apiFetch(`/api/v1/brands/${brandId}/pattern-decay`);
}
