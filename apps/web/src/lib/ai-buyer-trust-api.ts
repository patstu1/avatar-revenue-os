/**
 * Public API wrapper for the AI Buyer Trust Test.
 *
 * No auth required. Posts to the FastAPI route mounted at
 * /api/v1/ai-search-authority/score. Returns the public-result envelope or
 * a structured error.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window !== "undefined" ? window.location.origin : "");

export type TrustTestSubmit = {
  website_url: string;
  company_name: string;
  industry: string;
  contact_email: string;
  competitor_url?: string;
  city_or_market?: string;
  /** Honeypot — humans never fill this; bots that auto-complete by name
   * do. Always sent (empty string for humans), value rejected by the
   * backend if non-empty. */
  bot_field?: string;
};

export type TrustTestGap = {
  public_label: string;
  score: number;
  detected: string[];
  missing: string[];
  why_it_matters: string;
  recommended_fix: string;
};

export type TrustTestBuyerQuestion = {
  question: string;
  rationale: string;
};

export type TrustTestResult = {
  report_id: string;
  status: string;
  submitted: {
    company_name: string;
    website_url: string;
    industry: string;
  };
  total_score: number;
  authority_score: number;
  score_label:
    | "not_ready"
    | "weak"
    | "developing"
    | "strong"
    | "authority_ready"
    | "not_assessed";
  confidence_label: "low" | "medium" | "high";
  top_gaps: TrustTestGap[];
  quick_win: string | null;
  buyer_questions_preview: TrustTestBuyerQuestion[];
  recommended_package: {
    primary_slug: string | null;
    secondary_slug: string | null;
    creative_proof_slug: string | null;
    rationale: string;
  };
  cta: { label: string; href: string };
  platform_hint: {
    first_snapshot: string;
    monitoring: string;
    history: string;
    graph: string;
  };
  report_version: string;
  disclaimer: string;
  fetch_error?: string | null;
};

export type TrustTestErrorBody = {
  detail: { field?: string; message?: string } | string;
};

export class TrustTestError extends Error {
  field: string | null;
  status: number;
  constructor(message: string, status: number, field: string | null) {
    super(message);
    this.field = field;
    this.status = status;
  }
}

export async function submitTrustTest(
  payload: TrustTestSubmit,
): Promise<TrustTestResult> {
  // Always send bot_field — humans send empty string, bots fill it.
  const body: TrustTestSubmit = {
    bot_field: "",
    ...payload,
  };
  const resp = await fetch(`${API_BASE}/api/v1/ai-search-authority/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    let body: TrustTestErrorBody | null = null;
    try {
      body = (await resp.json()) as TrustTestErrorBody;
    } catch {
      // ignore
    }
    let field: string | null = null;
    let message = `Request failed (${resp.status})`;
    if (body && body.detail) {
      if (typeof body.detail === "string") {
        message = body.detail;
      } else {
        field = body.detail.field ?? null;
        message = body.detail.message ?? message;
      }
    }
    throw new TrustTestError(message, resp.status, field);
  }
  return (await resp.json()) as TrustTestResult;
}

export type SnapshotReviewResponse = {
  report_id: string;
  report_status: string;
  message: string;
};

export async function requestSnapshotReview(
  reportId: string,
): Promise<SnapshotReviewResponse> {
  const resp = await fetch(
    `${API_BASE}/api/v1/ai-search-authority/reports/${reportId}/request-snapshot-review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    },
  );
  if (!resp.ok) {
    let body: TrustTestErrorBody | null = null;
    try {
      body = (await resp.json()) as TrustTestErrorBody;
    } catch {
      // ignore
    }
    let message = `Request failed (${resp.status})`;
    if (body && body.detail) {
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail.message) message = body.detail.message;
    }
    throw new TrustTestError(message, resp.status, null);
  }
  return (await resp.json()) as SnapshotReviewResponse;
}
