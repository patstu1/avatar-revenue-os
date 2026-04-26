/**
 * sitemap.xml — must include every public marketing surface (package,
 * about, FAQ, comparison, industry, authority pages) so search and AI
 * crawlers discover them without relying on internal links from the
 * /login-redirected home page.
 */

import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/proofhook-packages";

const NOW = new Date();

const PATHS: { path: string; priority: number; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"] }[] = [
  // ── Authority / package landing ─────────────────────────────────────
  { path: "/ai-search-authority", priority: 0.9, changeFrequency: "monthly" },
  { path: "/services/ai-search-authority", priority: 0.7, changeFrequency: "monthly" },

  // ── Standard marketing pages ────────────────────────────────────────
  { path: "/faq", priority: 0.8, changeFrequency: "monthly" },
  { path: "/how-it-works", priority: 0.8, changeFrequency: "monthly" },

  // ── Comparison pages ────────────────────────────────────────────────
  { path: "/compare/proofhook-vs-content-agency", priority: 0.7, changeFrequency: "monthly" },
  { path: "/compare/proofhook-vs-ugc-platform", priority: 0.7, changeFrequency: "monthly" },

  // ── Industry / vertical context pages (NOT niche-locked packages) ──
  { path: "/industries/ai-startups", priority: 0.7, changeFrequency: "monthly" },
  { path: "/industries/saas", priority: 0.7, changeFrequency: "monthly" },
  { path: "/industries/ecommerce", priority: 0.7, changeFrequency: "monthly" },
];

export default function sitemap(): MetadataRoute.Sitemap {
  return PATHS.map(({ path, priority, changeFrequency }) => ({
    url: `${SITE_URL}${path}`,
    lastModified: NOW,
    changeFrequency,
    priority,
  }));
}
