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
  // ── Entity / authority / package landing ───────────────────────────
  { path: "/about", priority: 0.9, changeFrequency: "monthly" },
  { path: "/ai-search-authority", priority: 0.9, changeFrequency: "monthly" },
  { path: "/services/ai-search-authority", priority: 0.6, changeFrequency: "monthly" },
  { path: "/ai-buyer-trust-test", priority: 0.95, changeFrequency: "weekly" },

  // ── Standard marketing pages ────────────────────────────────────────
  { path: "/faq", priority: 0.8, changeFrequency: "monthly" },
  { path: "/how-it-works", priority: 0.8, changeFrequency: "monthly" },
  { path: "/proof", priority: 0.8, changeFrequency: "monthly" },
  { path: "/examples", priority: 0.7, changeFrequency: "monthly" },

  // ── Comparison pages ────────────────────────────────────────────────
  { path: "/compare/proofhook-vs-content-agency", priority: 0.7, changeFrequency: "monthly" },
  { path: "/compare/proofhook-vs-ugc-platform", priority: 0.7, changeFrequency: "monthly" },

  // ── Industry / vertical context pages (NOT niche-locked packages) ──
  { path: "/industries/ai-startups", priority: 0.7, changeFrequency: "monthly" },
  { path: "/industries/saas", priority: 0.7, changeFrequency: "monthly" },
  { path: "/industries/ecommerce", priority: 0.7, changeFrequency: "monthly" },

  // ── Answer-engine pages — direct buyer-question answers ────────────
  { path: "/answers/what-is-proof-based-content", priority: 0.7, changeFrequency: "monthly" },
  { path: "/answers/proof-content-vs-ugc", priority: 0.7, changeFrequency: "monthly" },
  { path: "/answers/how-much-do-short-form-content-packages-cost", priority: 0.7, changeFrequency: "monthly" },
  { path: "/answers/best-content-package-for-founder-led-brands", priority: 0.7, changeFrequency: "monthly" },
  { path: "/answers/how-to-make-a-company-ai-searchable", priority: 0.7, changeFrequency: "monthly" },
  { path: "/answers/what-is-ai-search-authority", priority: 0.7, changeFrequency: "monthly" },
  { path: "/answers/how-to-get-cited-by-ai-search-engines", priority: 0.7, changeFrequency: "monthly" },
];

export default function sitemap(): MetadataRoute.Sitemap {
  return PATHS.map(({ path, priority, changeFrequency }) => ({
    url: `${SITE_URL}${path}`,
    lastModified: NOW,
    changeFrequency,
    priority,
  }));
}
