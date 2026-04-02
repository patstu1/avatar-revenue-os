const API = process.env.NEXT_PUBLIC_API_URL ?? "https://app.nvironments.com/api/v1";

function headers() {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  return { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

export async function fetchCreatorRevenueOpportunities(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/creator-revenue-opportunities`, { headers: headers() });
  return r.json();
}
export async function recomputeCreatorRevenueOpportunities(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/creator-revenue-opportunities/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
export async function fetchUgcServices(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/ugc-services`, { headers: headers() });
  return r.json();
}
export async function recomputeUgcServices(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/ugc-services/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
export async function fetchServiceConsulting(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/service-consulting`, { headers: headers() });
  return r.json();
}
export async function recomputeServiceConsulting(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/service-consulting/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
export async function fetchPremiumAccess(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/premium-access`, { headers: headers() });
  return r.json();
}
export async function recomputePremiumAccess(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/premium-access/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
export async function fetchLicensing(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/licensing`, { headers: headers() });
  return r.json();
}
export async function recomputeLicensing(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/licensing/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
export async function fetchSyndication(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/syndication`, { headers: headers() });
  return r.json();
}
export async function recomputeSyndication(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/syndication/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
export async function fetchDataProducts(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/data-products`, { headers: headers() });
  return r.json();
}
export async function recomputeDataProducts(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/data-products/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
export async function fetchMerch(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/merch`, { headers: headers() });
  return r.json();
}
export async function recomputeMerch(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/merch/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
export async function fetchLiveEvents(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/live-events`, { headers: headers() });
  return r.json();
}
export async function recomputeLiveEvents(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/live-events/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
export async function fetchOwnedAffiliateProgram(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/owned-affiliate-program`, { headers: headers() });
  return r.json();
}
export async function recomputeOwnedAffiliateProgram(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/owned-affiliate-program/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
export async function fetchCreatorRevenueHub(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/creator-revenue-hub`, { headers: headers() });
  return r.json();
}
export async function recomputeCreatorRevenueHub(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/creator-revenue-hub/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
export async function fetchCreatorRevenueTruth(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/creator-revenue-truth`, { headers: headers() });
  return r.json();
}
export async function fetchCreatorRevenueBlockers(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/creator-revenue-blockers`, { headers: headers() });
  return r.json();
}
export async function recomputeCreatorRevenueBlockers(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/creator-revenue-blockers/recompute`, { method: "POST", headers: headers() });
  return r.json();
}
export async function fetchCreatorRevenueEvents(brandId: string) {
  const r = await fetch(`${API}/brands/${brandId}/creator-revenue-events`, { headers: headers() });
  return r.json();
}
