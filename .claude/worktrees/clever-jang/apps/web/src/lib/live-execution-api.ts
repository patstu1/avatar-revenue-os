const BASE = process.env.NEXT_PUBLIC_API_URL ?? (typeof window !== "undefined" ? window.location.origin : "http://localhost:8001");
const API = `${BASE.replace(/\/+$/, "")}/api/v1`;

function headers() {
  const token = typeof window !== "undefined" ? localStorage.getItem("aro_token") : null;
  return { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

// ── Analytics ──────────────────────────────────────────────
export async function fetchAnalyticsImports(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/analytics-imports`, { headers: headers() });
  return r.json();
}

export async function createAnalyticsImport(brandId: string, body: { source: string; source_category?: string; events: any[] }) {
  const r = await fetch(`${API}/brands/${brandId}/analytics-imports`, { method: "POST", headers: headers(), body: JSON.stringify(body) });
  return r.json();
}

export async function fetchAnalyticsEvents(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/analytics-events`, { headers: headers() });
  return r.json();
}

export async function recomputeAnalytics(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/analytics-events/recompute`, { method: "POST", headers: headers() });
  return r.json();
}

// ── Conversions ────────────────────────────────────────────
export async function fetchConversionImports(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/conversion-imports`, { headers: headers() });
  return r.json();
}

export async function createConversionImport(brandId: string, body: { source: string; source_category?: string; conversions: any[] }) {
  const r = await fetch(`${API}/brands/${brandId}/conversion-imports`, { method: "POST", headers: headers(), body: JSON.stringify(body) });
  return r.json();
}

export async function fetchConversionEvents(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/conversion-events`, { headers: headers() });
  return r.json();
}

export async function recomputeConversions(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/conversion-events/recompute`, { method: "POST", headers: headers() });
  return r.json();
}

// ── Experiment Truth ───────────────────────────────────────
export async function fetchExperimentImports(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/experiment-observation-imports`, { headers: headers() });
  return r.json();
}

export async function createExperimentImport(brandId: string, body: { source: string; observations: any[] }) {
  const r = await fetch(`${API}/brands/${brandId}/experiment-observation-imports`, { method: "POST", headers: headers(), body: JSON.stringify(body) });
  return r.json();
}

export async function fetchExperimentLiveResults(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/experiment-live-results`, { headers: headers() });
  return r.json();
}

export async function recomputeExperimentTruth(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/experiment-live-results/recompute`, { method: "POST", headers: headers() });
  return r.json();
}

// ── CRM ────────────────────────────────────────────────────
export async function fetchCrmContacts(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/crm-contacts`, { headers: headers() });
  return r.json();
}

export async function createCrmContact(brandId: string, body: { email?: string; phone?: string; name?: string; segment?: string; lifecycle_stage?: string; source?: string; tags?: string[] }) {
  const r = await fetch(`${API}/brands/${brandId}/crm-contacts`, { method: "POST", headers: headers(), body: JSON.stringify(body) });
  return r.json();
}

export async function fetchCrmSyncs(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/crm-syncs`, { headers: headers() });
  return r.json();
}

export async function runCrmSync(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/crm-syncs/recompute`, { method: "POST", headers: headers() });
  return r.json();
}

// ── Email ──────────────────────────────────────────────────
export async function fetchEmailRequests(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/email-send-requests`, { headers: headers() });
  return r.json();
}

export async function createEmailSend(brandId: string, body: { to_email: string; subject: string; body_html?: string; body_text?: string; template_id?: string; provider?: string }) {
  const r = await fetch(`${API}/brands/${brandId}/email-send-requests`, { method: "POST", headers: headers(), body: JSON.stringify(body) });
  return r.json();
}

// ── SMS ────────────────────────────────────────────────────
export async function fetchSmsRequests(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/sms-send-requests`, { headers: headers() });
  return r.json();
}

export async function createSmsSend(brandId: string, body: { to_phone: string; message_body: string; provider?: string }) {
  const r = await fetch(`${API}/brands/${brandId}/sms-send-requests`, { method: "POST", headers: headers(), body: JSON.stringify(body) });
  return r.json();
}

// ── Messaging Blockers ─────────────────────────────────────
export async function fetchMessagingBlockers(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/messaging-blockers`, { headers: headers() });
  return r.json();
}

export async function recomputeMessagingBlockers(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/messaging-blockers/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
