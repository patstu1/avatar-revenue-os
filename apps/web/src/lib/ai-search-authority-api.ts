/**
 * Operator-side API wrapper for the AI Buyer Trust Test reports.
 * Reuses apiFetch from @/lib/api so the auth token + base URL are
 * consistent with the rest of the operator dashboard.
 */

import { apiFetch } from "@/lib/api";

export type AuthorityReportListItem = {
  id: string;
  company_name: string;
  website_url: string;
  website_domain: string;
  contact_email: string;
  industry: string;
  total_score: number;
  score_label: string;
  confidence_label: string;
  recommended_package_slug: string | null;
  report_status: string;
  top_gap_label: string | null;
  lead_opportunity_id: string | null;
  created_at: string | null;
};

export type AuthorityReportList = {
  items: AuthorityReportListItem[];
  count: number;
  limit: number;
  offset: number;
};

export type AuthorityReportDetail = AuthorityReportListItem & {
  organization_id: string;
  brand_id: string | null;
  competitor_url: string | null;
  city_or_market: string | null;
  confidence: number;
  dimension_scores: Record<string, number>;
  technical_scores: Record<string, number>;
  evidence: Record<string, unknown>;
  raw_signals: Record<string, unknown>;
  scanned_pages: Array<Record<string, unknown>>;
  top_gaps: Array<Record<string, unknown>>;
  quick_wins: string[];
  authority_score: number;
  authority_graph: Record<string, unknown>;
  buyer_questions: Array<{ question: string; rationale: string }>;
  recommended_pages: Array<Record<string, unknown>>;
  recommended_schema: Array<Record<string, unknown>>;
  recommended_proof_assets: Array<Record<string, unknown>>;
  recommended_comparison_surfaces: Array<Record<string, unknown>>;
  monitoring_recommendation: string | null;
  ai_summary: string | null;
  public_result: Record<string, unknown>;
  scan_started_at: string | null;
  scan_completed_at: string | null;
  fetch_error: string | null;
  formula_version: string;
  report_version: string;
  scan_version: string;
  updated_at: string | null;
};

export const aiSearchAuthorityApi = {
  list: (params?: {
    limit?: number;
    offset?: number;
    status?: string;
    score_min?: number;
    score_max?: number;
    package_slug?: string;
    search?: string;
  }) => {
    const search = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") {
          search.set(k, String(v));
        }
      });
    }
    const qs = search.toString();
    return apiFetch<AuthorityReportList>(
      `/api/v1/ai-search-authority/reports${qs ? "?" + qs : ""}`,
    );
  },
  detail: (id: string) =>
    apiFetch<AuthorityReportDetail>(
      `/api/v1/ai-search-authority/reports/${id}`,
    ),
  markQualified: (id: string) =>
    apiFetch<{ id: string; report_status: string }>(
      `/api/v1/ai-search-authority/reports/${id}/mark-qualified`,
      { method: "POST" },
    ),
  archive: (id: string) =>
    apiFetch<{ id: string; report_status: string }>(
      `/api/v1/ai-search-authority/reports/${id}/archive`,
      { method: "POST" },
    ),
};
