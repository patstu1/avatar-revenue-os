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

export type ProofHookLane = "ai_authority" | "creative_proof";

export type ProofHookPackage = {
  slug: string;
  name: string;
  /** USD price for the package's first/full unit. "From" pricing where the
   * engagement is variable — surfaces in copy as "Starting at $X". */
  price: number;
  priceFrom?: boolean;
  /** Override the rendered price string for non-numeric pricing
   * (e.g. "Free with email", "Custom"). Public surfaces should always
   * show "Starting at" for numeric rungs and respect this override for
   * the others. */
  priceDisplayOverride?: string;
  /** Short tagline rendered in cards/listings. */
  tagline: string;
  /** Long-form positioning paragraph (1–2 sentences). */
  positioning: string;
  /** Buyer-facing description of who this package fits. Rendered above
   * the deliverables list on the package grid. */
  whoItsFor: string;
  /** Bullet list of what the buyer gets. */
  deliverables: string[];
  /** Engagement timeline as a human-readable string ("7 days", "10–14 days"). */
  timeline: string;
  /** Public marketing URL on the ProofHook site. May be a deep link to
   * /services/{slug} or its own dedicated path. */
  url: string;
  /** Whether this package has its own dedicated detail page on the site. */
  hasDetailPage: boolean;
  /** Which product lane this package belongs to. Drives grouping on the
   * homepage and the cross-lane recommendation labels in the test
   * result. */
  lane: ProofHookLane;
};

/** Rendered price string per the public pricing rules:
 *   - priceDisplayOverride wins when set ("Free with email", "Custom")
 *   - priceFrom=true → "Starting at $X"
 *   - otherwise → "$X"
 */
export function packagePriceDisplay(pkg: ProofHookPackage): string {
  if (pkg.priceDisplayOverride) return pkg.priceDisplayOverride;
  const formatted = `$${pkg.price.toLocaleString()}`;
  return pkg.priceFrom ? `Starting at ${formatted}` : formatted;
}

export const ORG_ID = "eb0fd0c0-03dd-40a9-9cb7-795e50aa8705";
export const BRAND_ID = "e935f70d-090d-4354-9c52-263deab31cc8";

export const PACKAGES: ProofHookPackage[] = [
  {
    slug: "signal_entry",
    name: "UGC Starter Pack",
    price: 1500,
    tagline: "Lowest-friction entry into ProofHook short-form creative.",
    whoItsFor:
      "Founder-led brands and SaaS teams who want to validate ProofHook's voice and pacing before scaling spend.",
    lane: "creative_proof",
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
    name: "Proof Video Pack",
    price: 2500,
    tagline: "Recurring proof-anchored short-form videos that fill new authority surfaces.",
    whoItsFor:
      "Businesses that need a steady cadence of proof-anchored short-form videos to populate case-study, testimonial, and outcome pages.",
    lane: "creative_proof",
    positioning:
      "A first-month engagement that produces 8–12 short-form proof videos, multiple hooks per concept, two CTA angles, and a monthly refresh cadence so the new authority surfaces stay populated.",
    deliverables: [
      "8–12 short-form proof video assets per month",
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
    name: "Hook Pack",
    price: 3500,
    tagline: "Hook + angle rebuild aligned to the offer pages the AI Authority work publishes.",
    whoItsFor:
      "Brands whose offer clarity is already good in copy but needs sharper hooks and angles to convert paid traffic.",
    lane: "creative_proof",
    positioning:
      "An end-to-end creative audit of existing short-form output, a rebuild of hooks and angles against the offer, and a concrete production roadmap that pairs cleanly with the AI Search Authority Sprint.",
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
    name: "Paid Social Creative Pack",
    price: 4500,
    tagline: "Paid-media-ready creative + hook variations + monthly optimization.",
    whoItsFor:
      "Teams running paid social where creative throughput and hook variation directly drive CAC.",
    lane: "creative_proof",
    positioning:
      "First-month build of 12–20 short-form assets with hook variations, plus offer/landing support and monthly optimization tied to paid-media performance. Pairs with Authority Monitoring so the offer surface stays current as the creative iterates.",
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
    name: "Founder Clip Pack",
    price: 5000,
    tagline: "Founder-led launch-anchored clips with a focused hook set and compressed delivery.",
    whoItsFor:
      "Founders running a launch window or a brand moment where founder-on-camera clips carry the credibility lift.",
    lane: "creative_proof",
    positioning:
      "Fast-turn batch of founder-led, launch-anchored clips with a focused hook set, CTA alignment with the launch offer, and compressed delivery on a launch timeline.",
    deliverables: [
      "Launch-anchored founder clip batch",
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
    name: "Creative Retainer",
    price: 7500,
    tagline: "High-throughput recurring creative production with priority turnaround.",
    whoItsFor:
      "Brands running multiple campaigns or audiences in parallel that need consistent multi-angle creative every month.",
    lane: "creative_proof",
    positioning:
      "Recurring creative production engagement: multi-angle hooks, offer and landing-page support, priority turnaround, and a high-throughput first-month build. Pairs with Authority Monitoring so the underlying offer surfaces stay in lockstep with the creative.",
    deliverables: [
      "Recurring creative production at upper-throughput cadence",
      "Multi-angle hooks per concept",
      "Offer and landing-page support",
      "Priority turnaround",
    ],
    timeline: "Monthly",
    url: "/services/creative-command",
    hasDetailPage: false,
  },
  {
    slug: "ai_search_authority_snapshot",
    name: "AI Buyer Trust Snapshot",
    price: 0,
    priceDisplayOverride: "Free with email",
    lane: "ai_authority",
    whoItsFor:
      "Businesses ready for an operator-reviewed read on how clearly AI-assisted buyers can understand and trust them.",
    tagline:
      "A reviewed Authority Snapshot that maps how clearly AI-assisted buyers can understand and trust your business.",
    positioning:
      "A diagnostic of the public signals AI search systems and AI-assisted buyers read about your business — entity, audience, offers, proof, comparisons, schema, FAQ depth, trust signals — with a prioritized fix list and recommended next steps. Reviewed by a ProofHook operator before delivery. Free for early-adopter founding clients while we build out the platform.",
    deliverables: [
      "Reviewed Authority Snapshot (PDF)",
      "Per-dimension evidence: detected, missing, why it matters, recommended fix",
      "5–10 buyer questions you should be prepared to answer publicly",
      "Recommended pages, schema, and proof assets",
      "Recommended package + scoping note",
    ],
    timeline: "3–5 days",
    url: "/ai-search-authority/snapshot",
    hasDetailPage: false,
  },
  {
    slug: "ai_search_authority_sprint",
    name: "AI Search Authority Sprint",
    price: 1500,
    priceFrom: true,
    lane: "ai_authority",
    whoItsFor:
      "Founder-led brands, SaaS, AI, and service businesses with weak entity presence, thin offer pages, or low schema coverage.",
    tagline:
      "Build the AI Buyer Trust Infrastructure that makes your business easier to understand, compare, and trust.",
    positioning:
      "Founding-client launch pricing. The Sprint builds authority infrastructure — entity surfaces, answer-engine pages, FAQ structure, comparison surfaces, schema, and trust scaffolding. ProofHook structures the inputs the AI decision layer reads when it evaluates your business.",
    deliverables: [
      "AI Buyer Trust audit + Authority Graph",
      "robots.txt and crawler access review",
      "sitemap and canonical URL review",
      "Schema implementation plan + assets",
      "Organization / WebSite / Service / Product / Offer JSON-LD",
      "FAQPage + BreadcrumbList JSON-LD",
      "Entity / About page",
      "FAQ architecture (top 8 buyer questions)",
      "How-it-works page",
      "2 industry pages",
      "2 comparison surfaces",
      "5 answer-engine pages",
      "Internal linking map",
      "Google Search Console + Bing Webmaster checklists",
      "AI referral tracking plan",
      "External citation / backlink target checklist",
    ],
    timeline: "10–14 days",
    url: "/services/ai-search-authority",
    hasDetailPage: true,
  },
  {
    slug: "proof_infrastructure_buildout",
    name: "Proof Infrastructure Buildout",
    price: 5000,
    priceFrom: true,
    lane: "ai_authority",
    whoItsFor:
      "Brands whose Authority Snapshot shows missing proof pages, no comparison surfaces, and offer pages that AI assistants cannot read or summarize.",
    tagline:
      "Publish the load-bearing authority surfaces — answer pages, proof pages, comparisons, schema, and internal linking — that AI assistants and buyers can both read.",
    positioning:
      "Founding-client launch pricing. For businesses whose Authority Score signals low offer clarity, missing proof, and no comparison surface. The Buildout ships the authority infrastructure the Sprint identifies — not blog posts or generic content — so machine-readable trust compounds across every page added.",
    deliverables: [
      "Service / product / category pages with Service or Product JSON-LD",
      "Proof, case-study, and testimonial pages with Review / AggregateRating where supported",
      "FAQ architecture with FAQPage JSON-LD",
      "Competitor comparison + 'best {category}' + 'how to choose' surfaces",
      "Authority Graph wiring (internal linking + breadcrumb schema)",
      "Conversion / CTA structure tied to the offer ladder",
    ],
    timeline: "3–6 weeks",
    url: "/ai-search-authority",
    hasDetailPage: false,
  },
  {
    slug: "authority_monitoring_retainer",
    name: "Authority Monitoring Retainer",
    price: 1500,
    priceFrom: true,
    priceDisplayOverride: "Starting at $1,500/month",
    lane: "ai_authority",
    whoItsFor:
      "Companies already at a strong Authority Score that need to keep score, schema, FAQ, comparison, and proof surfaces current as buyer questions and competitors change.",
    tagline:
      "Keep the Authority Graph current — score changes, schema drift, new buyer questions, comparison gaps, and proof updates tracked monthly.",
    positioning:
      "For businesses already at a strong Authority Score that need to keep it. Monthly authority re-scoring, schema drift fixes, new comparison pages when a relevant alternative appears, FAQ refresh against newly-detected buyer questions, proof updates, crawl/index status checks, and lead/revenue impact tracking where available.",
    deliverables: [
      "Monthly Authority Score re-scan with diff vs. prior month",
      "Schema audit + drift fixes",
      "FAQ refresh against new buyer questions detected each month",
      "New comparison surface when a new alternative shows up in search",
      "Proof page refresh + new credentials surfaced",
      "Crawl/index status check (Search Console + Bing Webmaster)",
      "Lead and revenue impact reporting where the data exists",
    ],
    timeline: "Monthly retainer",
    url: "/ai-search-authority",
    hasDetailPage: false,
  },
  {
    slug: "ai_search_authority_system",
    name: "AI Search Authority System",
    price: 0,
    priceDisplayOverride: "Custom",
    lane: "ai_authority",
    whoItsFor:
      "Larger companies, multi-location businesses, SaaS, clinics, agencies, and B2B service companies whose authority surface spans multiple brands, locations, products, or buyer journeys.",
    tagline:
      "Custom authority system for larger companies, multi-location businesses, SaaS, clinics, agencies, and B2B service companies.",
    positioning:
      "Custom-scoped engagement for organizations whose authority surface spans multiple brands, locations, products, or buyer journeys. Combines Sprint, Buildout, and Monitoring under a single operator-led plan with custom scope per business unit.",
    deliverables: [
      "Custom Authority System scoping",
      "Per-brand / per-location authority surfaces",
      "Custom schema graph",
      "Cross-brand internal linking and proof-asset network",
      "Operator-led monthly review cycle",
    ],
    timeline: "Custom",
    url: "/ai-search-authority",
    hasDetailPage: false,
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
