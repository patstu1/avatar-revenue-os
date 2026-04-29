/**
 * Frontend client for the ProofHook AI Buyer Trust Test backend.
 *
 * The two public functions (`submitScore`, `requestSnapshotReview`) reach
 * `/api/v1/ai-search-authority/*` on the FastAPI service mounted at
 * `NEXT_PUBLIC_API_URL`. They never require authentication — the public
 * endpoints accept anonymous submissions on purpose.
 *
 * The operator-only functions (`listReports`, `getReport`, `createProposal`)
 * use the existing `apiFetch` helper which attaches the operator's bearer
 * token from `localStorage` and handles 401 redirects.
 *
 * Purpose: this module is the contract. The standalone ProofHook public
 * frontend (separate repo) imports the equivalent surface; the Next app
 * dashboard uses the operator functions when surfacing reports inside
 * the Revenue OS console. The marketing pages in this Next app are NOT
 * modified by this file.
 */

import { apiFetch, API_BASE } from "./api";

export type ScoreSubmitRequest = {
  submitter_email: string;
  submitter_name?: string;
  submitter_company?: string;
  submitter_url?: string;
  submitter_role?: string;
  submitter_revenue_band?: string;
  vertical?: string;
  buyer_type?: string;
  industry_context?: string;
  answers?: Record<string, "yes" | "no" | "unknown" | string | boolean>;
  notes?: string;
};

export type GapItem = {
  key: string;
  label: string;
  weight: number;
  severity: "high" | "medium" | "low" | string;
};

export type ScoreSubmitResponse = {
  report_id: string;
  score: number;
  tier: "cold" | "warm" | "hot" | string;
  gaps: GapItem[];
  quick_win: string;
  recommended_package_slug: string;
  recommended_package_path: string;
  diagnostic_kind: "answer_based";
  status: string;
};

export type SnapshotReviewResponse = {
  report_id: string;
  status: string;
  snapshot_requested_at: string;
  deduped: boolean;
};

export type ReportListItem = {
  id: string;
  submitter_email: string;
  submitter_company: string;
  score: number;
  tier: string;
  recommended_package_slug: string;
  status: string;
  vertical: string;
  created_at: string;
};

export type ReportDetail = ReportListItem & {
  organization_id: string | null;
  brand_id: string | null;
  submitter_name: string;
  submitter_url: string;
  submitter_role: string;
  submitter_revenue_band: string;
  buyer_type: string;
  industry_context: string;
  answers_json: Record<string, unknown> | null;
  gaps_json: Array<Record<string, unknown>> | null;
  quick_win: string;
  snapshot_requested_at: string | null;
  proposal_created_at: string | null;
  closed_at: string | null;
  lead_opportunity_id: string | null;
  proposal_id: string | null;
  source: string;
  notes: string | null;
  updated_at: string;
};

export type CreateProposalRequest = {
  package_slug?: string;
  title?: string;
  summary?: string;
  unit_amount_cents_override?: number;
  currency?: string;
  notes?: string;
};

export type CreateProposalResponse = {
  report_id: string;
  proposal_id: string;
  package_slug: string;
  total_amount_cents: number;
  currency: string;
  status: string;
};

const ROOT = "/api/v1/ai-search-authority";

// ── Public ──────────────────────────────────────────────────────────

export async function submitScore(
  body: ScoreSubmitRequest,
): Promise<ScoreSubmitResponse> {
  // The public endpoint does not require auth — bypass the apiFetch
  // 401-redirect path and post directly.
  const res = await fetch(`${API_BASE}${ROOT}/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`submitScore failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

export async function requestSnapshotReview(
  reportId: string,
): Promise<SnapshotReviewResponse> {
  const res = await fetch(
    `${API_BASE}${ROOT}/reports/${encodeURIComponent(reportId)}/request-snapshot-review`,
    { method: "POST", headers: { "Content-Type": "application/json" } },
  );
  if (!res.ok) {
    throw new Error(
      `requestSnapshotReview failed: ${res.status} ${await res.text()}`,
    );
  }
  return res.json();
}

// ── Operator (auth-required) ────────────────────────────────────────

export async function listReports(opts?: {
  limit?: number;
  offset?: number;
  status?: string;
}): Promise<ReportListItem[]> {
  const params = new URLSearchParams();
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  if (opts?.status) params.set("status", opts.status);
  const qs = params.toString();
  return apiFetch<ReportListItem[]>(`${ROOT}/reports${qs ? `?${qs}` : ""}`);
}

export async function getReport(reportId: string): Promise<ReportDetail> {
  return apiFetch<ReportDetail>(
    `${ROOT}/reports/${encodeURIComponent(reportId)}`,
  );
}

export async function createProposal(
  reportId: string,
  body: CreateProposalRequest = {},
): Promise<CreateProposalResponse> {
  return apiFetch<CreateProposalResponse>(
    `${ROOT}/reports/${encodeURIComponent(reportId)}/create-proposal`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export const proofhookApi = {
  submitScore,
  requestSnapshotReview,
  listReports,
  getReport,
  createProposal,
};
