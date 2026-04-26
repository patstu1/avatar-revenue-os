/**
 * Single source of truth for ProofHook service packages used on the public
 * marketing pages and their JSON-LD. Mirrors what's stamped on the public
 * Stripe Payment Link metadata (org_id, brand_id, package_slug) so the
 * marketing surface, the structured data, and the buyer-side webhook chain
 * agree on the same package identifiers. NOT used to create payments —
 * existing Stripe Payment Links handle that. This module is read-only metadata.
 *
 * Universal-package rule:
 *   ProofHook packages are universal. The seven slugs below are the only
 *   public-facing package identities. Industry / vertical / buyer_type are
 *   CONTEXT (lead source, page context, intake answer, optional metadata),
 *   never package identity. Do NOT add niche-named entries like
 *   "Beauty Content Pack" or "SaaS Content Pack" — those collapse the
 *   addressable market and fragment revenue truth.
 *
 *   Metadata flows on the Stripe → webhook → Payment chain:
 *     - package_slug         (required, universal — one of the seven below)
 *     - package_name         (required, universal display name)
 *     - vertical             (optional, lower-case slug — e.g. "saas",
 *                             "ai_startups", "ecommerce")
 *     - industry_context     (optional, free-text additional detail)
 *     - buyer_type           (optional — "founder_led", "agency", etc.)
 *     - source               (required — proofhook_public_checkout[_live])
 *     - fulfillment_type     (required — "content_pack" today)
 *
 *   Payment.metadata_json is JSONB — additional context keys are persisted
 *   verbatim by record_payment_from_stripe without code changes. Revenue
 *   reporting attributes to package_slug FIRST, vertical SECOND.
 *
 * Copy rules: never claim guaranteed rankings, guaranteed AI placement, or
 * guaranteed citations. Use "improve", "strengthen", "increase eligibility".
 */

export type ProofHookPackage = {
  slug: string;
  name: string;
  /** USD price for the package's first/full unit. "From" pricing where the
   * engagement is variable — surfaces in copy as "From $X". */
  price: number;
  priceFrom?: boolean;
  /** Short tagline rendered in cards/listings. */
  tagline: string;
  /** Long-form positioning paragraph (1–2 sentences). */
  positioning: string;
  /** Bullet list of what the buyer gets. */
  deliverables: string[];
  /** Engagement timeline as a human-readable string ("7 days", "10–14 days"). */
  timeline: string;
  /** Public marketing URL on the ProofHook site. May be a deep link to
   * /services/{slug} or its own dedicated path. */
  url: string;
  /** Whether this package has its own dedicated detail page on the site. */
  hasDetailPage: boolean;
};

export const ORG_ID = "eb0fd0c0-03dd-40a9-9cb7-795e50aa8705";
export const BRAND_ID = "e935f70d-090d-4354-9c52-263deab31cc8";

export const PACKAGES: ProofHookPackage[] = [
  {
    slug: "signal_entry",
    name: "Signal Entry",
    price: 1500,
    tagline: "Lowest-friction entry into ProofHook short-form creative.",
    positioning:
      "A four-asset short-form video pack with a seven-day turnaround — designed to validate ProofHook's voice and pacing on your brand before scaling spend.",
    deliverables: [
      "4 short-form video assets",
      "1 hook variant per asset",
      "7-day turnaround",
      "Asset delivery via download link",
    ],
    timeline: "7 days",
    url: "/services/signal-entry",
    hasDetailPage: false,
  },
  {
    slug: "momentum_engine",
    name: "Momentum Engine",
    price: 2500,
    tagline: "Monthly creative engine for sustained short-form output.",
    positioning:
      "A first-month engagement that produces 8–12 short-form assets, multiple hooks per concept, two CTA angles, and a monthly refresh cadence.",
    deliverables: [
      "8–12 short-form video assets per month",
      "Multiple hook variants per asset",
      "2 CTA angles",
      "Monthly refresh cadence",
    ],
    timeline: "Monthly",
    url: "/services/momentum-engine",
    hasDetailPage: false,
  },
  {
    slug: "conversion_architecture",
    name: "Conversion Architecture",
    price: 3500,
    tagline: "Full creative audit + hook/angle rebuild + offer alignment.",
    positioning:
      "An end-to-end creative audit of your existing short-form output, a rebuild of hooks and angles against the offer, and a concrete production roadmap.",
    deliverables: [
      "Creative audit of existing short-form output",
      "Hook and angle rebuild",
      "Offer alignment review",
      "Production roadmap",
    ],
    timeline: "10–14 days",
    url: "/services/conversion-architecture",
    hasDetailPage: false,
  },
  {
    slug: "paid_media_engine",
    name: "Paid Media Engine",
    price: 4500,
    tagline: "Recurring paid-media-ready creative + monthly optimization.",
    positioning:
      "First-month build of 12–20 short-form assets with hook variations, plus offer/landing support and monthly optimization tied to paid-media performance.",
    deliverables: [
      "12–20 short-form assets in month one",
      "Hook variations per asset",
      "Offer and landing page support",
      "Monthly optimization review",
    ],
    timeline: "Monthly",
    url: "/services/paid-media-engine",
    hasDetailPage: false,
  },
  {
    slug: "launch_sequence",
    name: "Launch Sequence",
    price: 5000,
    tagline: "Compressed launch-focused asset batch.",
    positioning:
      "Fast-turn batch of launch-focused short-form assets, a launch-specific hook set, CTA alignment with the launch offer, and compressed delivery on a launch timeline.",
    deliverables: [
      "Launch-focused asset batch",
      "Launch-specific hook set",
      "CTA alignment with the launch offer",
      "Compressed delivery timeline",
    ],
    timeline: "10–14 days",
    url: "/services/launch-sequence",
    hasDetailPage: false,
  },
  {
    slug: "creative_command",
    name: "Creative Command",
    price: 7500,
    tagline: "Recurring creative production at the upper end of throughput.",
    positioning:
      "Recurring creative production engagement: multi-angle hooks, offer and landing-page support, priority turnaround, and a high-throughput first-month build.",
    deliverables: [
      "Recurring creative production",
      "Multi-angle hooks",
      "Offer and landing-page support",
      "Priority turnaround",
    ],
    timeline: "Monthly",
    url: "/services/creative-command",
    hasDetailPage: false,
  },
  {
    slug: "ai_search_authority_sprint",
    name: "AI Search Authority Sprint",
    price: 4500,
    priceFrom: true,
    tagline:
      "Make your company easier for search engines and AI systems to understand, cite, and recommend.",
    positioning:
      "Improve machine readability, strengthen entity authority, and increase eligibility for search and AI discovery across Google, ChatGPT Search, Bing Copilot, Perplexity, and adjacent answer engines. We do not promise rankings or AI placements — we improve the inputs those systems use.",
    deliverables: [
      "AI search and entity audit",
      "robots.txt and crawler access review",
      "sitemap and canonical URL review",
      "Structured data / schema implementation plan",
      "Organization JSON-LD",
      "WebSite JSON-LD",
      "Service JSON-LD",
      "Product/Offer JSON-LD for core packages",
      "FAQPage JSON-LD",
      "BreadcrumbList JSON-LD",
      "About / entity page",
      "FAQ page",
      "How-it-works page",
      "2 industry pages",
      "2 comparison pages",
      "5 answer-engine content pages",
      "Internal linking map",
      "Google Search Console checklist",
      "Bing Webmaster Tools checklist",
      "AI referral tracking plan",
      "External citation / backlink target checklist",
    ],
    timeline: "10–14 days",
    url: "/services/ai-search-authority",
    hasDetailPage: true,
  },
];

export const PACKAGE_BY_SLUG: Record<string, ProofHookPackage> = Object.fromEntries(
  PACKAGES.map((p) => [p.slug, p])
);

/** Public site URL — used in JSON-LD canonical IDs and sitemap.
 * Reads NEXT_PUBLIC_SITE_URL with a sensible default (matches FRONTEND_URL
 * used by the API for emails). */
export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") ??
  "https://app.nvironments.com";

/** Canonical organization metadata (the buyer-facing brand). Mirrors the
 * brand row inserted in production for public-checkout attribution. */
export const ORG = {
  name: "ProofHook",
  legalName: "ProofHook",
  url: SITE_URL,
  logo: `${SITE_URL}/proofhook-logo.png`,
  description:
    "ProofHook helps founder-led brands, SaaS, AI, and service businesses produce paid-media-ready short-form creative and become easier for search engines and AI systems to understand and cite.",
  contactEmail: "hello@proofhook.com",
  sameAs: [] as string[],
};
