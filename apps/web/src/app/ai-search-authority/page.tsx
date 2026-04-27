import type { Metadata } from "next";
import Link from "next/link";

import { AiBuyerTrustTest } from "@/components/ai-buyer-trust/Test";
import {
  AfterTheTestSection,
  CommercialFlowSection,
  DecisionLayerSection,
  ExplainerVideoSection,
  ResultToPackageSection,
  ScatteredToStructuredSection,
  ThirdShiftSection,
  WhatProofHookChecksSection,
  WhatTheScoreRevealsSection,
} from "@/components/ai-buyer-trust/DecisionLayerSections";
import {
  CTA,
  MarketingShell,
  SectionHeading,
} from "@/components/marketing-shell";
import {
  FaqJsonLd,
  OrganizationJsonLd,
  PackageCatalogOffersJsonLd,
  ServiceJsonLd,
  WebSiteJsonLd,
} from "@/components/jsonld";
import {
  PACKAGE_BY_SLUG,
  SITE_URL,
  packagePriceDisplay,
} from "@/lib/proofhook-packages";

const SPRINT = PACKAGE_BY_SLUG["ai_search_authority_sprint"];
const SNAPSHOT = PACKAGE_BY_SLUG["ai_search_authority_snapshot"];
const BUILDOUT = PACKAGE_BY_SLUG["proof_infrastructure_buildout"];
const RETAINER = PACKAGE_BY_SLUG["authority_monitoring_retainer"];
const SYSTEM = PACKAGE_BY_SLUG["ai_search_authority_system"];

const PAGE_URL = "/ai-search-authority";

const FAQ = [
  {
    question: "How does ProofHook influence the AI decision layer?",
    answer:
      "ProofHook structures the inputs AI systems read when they evaluate a business — entity clarity, machine-readable proof, schema, FAQs, comparisons, trust signals, and crawlability. Clear inputs lead to clearer recommendations.",
  },
  {
    question: "How is this different from a generic AI SEO or GEO tool?",
    answer:
      "Generic AI SEO and GEO tools track citations and visibility from the outside. ProofHook builds the AI Buyer Trust Infrastructure those systems read — public proof, offers, FAQs, comparisons, schema, and trust structure — so your business is structured for the decision before it happens.",
  },
  {
    question: "What does the AI Search Authority Sprint include?",
    answer:
      "An AI Buyer Trust audit + Authority Graph, robots and crawler review, schema implementation plan and assets (Organization, WebSite, Service, Product/Offer, FAQPage, BreadcrumbList), entity / About / FAQ / how-it-works / industry / comparison / answer-engine pages, internal linking map, Search Console + Bing Webmaster checklists, and an AI referral tracking plan.",
  },
  {
    question: "Where does the AI Buyer Trust Snapshot fit?",
    answer:
      "The Snapshot is the reviewed Authority diagnostic. It is sized for businesses that want a deeper read than the public test before scoping a Sprint or Buildout, and it carries the same per-dimension evidence the Sprint will act on.",
  },
  {
    question: "How long is a Sprint engagement?",
    answer: "10–14 days from kickoff.",
  },
  {
    question: "What does a Sprint cost?",
    answer:
      "Founding-client launch pricing starts at $1,500. Final scope and price depend on the size of your existing site, the number of products or services to model, and the depth of structured data and content build-out.",
  },
  {
    question: "Who is this for?",
    answer:
      "Founder-led brands, SaaS companies, AI companies, service businesses, clinics, ecommerce brands, agencies, consultants, and premium local businesses that want their public surface to be clearer to both human buyers and AI assistants.",
  },
];

export const metadata: Metadata = {
  title: `AI Buyer Trust Infrastructure — ${SPRINT.name} | ProofHook`,
  description:
    "Google helped customers find businesses. AI is helping them decide who to trust. Take the AI Buyer Trust Test and see how clearly your business is structured for the AI decision layer.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
  openGraph: {
    title: `AI Buyer Trust Infrastructure | ProofHook`,
    description:
      "Customers are starting to ask AI systems who to trust, compare, and choose before they ever visit a website. ProofHook structures the public signals the AI decision layer reads.",
    url: `${SITE_URL}${PAGE_URL}`,
    type: "website",
  },
};

export default function AiSearchAuthorityPage() {
  return (
    <MarketingShell
      pageId="ai-search-authority"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "AI Buyer Trust", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <ServiceJsonLd pkg={SPRINT} pageUrl={PAGE_URL} />
      <PackageCatalogOffersJsonLd />
      <FaqJsonLd qa={FAQ} />

      {/* ── Hero ───────────────────────────────────────────────────── */}
      <section className="grid gap-10 sm:gap-12 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-start">
        <div>
          <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
            AI Buyer Trust Infrastructure
          </p>
          <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-tight text-zinc-100 sm:text-4xl">
            Will AI understand why customers should choose your business?
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-zinc-200 leading-relaxed">
            Google helped customers find businesses.
            <br />
            AI is helping them decide who to trust.
          </p>
          <p className="mt-4 max-w-2xl text-zinc-300 leading-relaxed">
            A new era of search is here — and it is bigger than Google.
            Customers are no longer browsing websites the same way. They
            are beginning to ask AI systems who to trust, compare, hire,
            and buy from before they ever reach a website.
          </p>
          <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
            ProofHook helps you see how clearly your business is structured
            for that decision layer.
          </p>
          <p className="mt-4 max-w-2xl text-sm text-zinc-400 leading-relaxed">
            Based on public website signals: offers, proof, FAQs, schema,
            comparisons, crawlability, and trust structure.
          </p>
        </div>
        <div className="lg:sticky lg:top-6">
          <AiBuyerTrustTest />
        </div>
      </section>

      {/* ── The third shift in search ──────────────────────────────── */}
      <ThirdShiftSection />

      {/* ── AI is becoming the decision layer ──────────────────────── */}
      <DecisionLayerSection />

      {/* ── Explainer video (placeholder + transcript-as-text) ─────── */}
      <ExplainerVideoSection />

      {/* ── What ProofHook checks ──────────────────────────────────── */}
      <WhatProofHookChecksSection />

      {/* ── What the score reveals ─────────────────────────────────── */}
      <WhatTheScoreRevealsSection />

      {/* ── From scattered proof to structured authority ──────────── */}
      <ScatteredToStructuredSection />

      {/* ── Result to package mapping ──────────────────────────────── */}
      <ResultToPackageSection />

      {/* ── Package ladder — full cards with whoItsFor + CTA ───────── */}
      <SectionHeading>AI Authority Packages</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Pick the package that fits the gap your Authority Score reveals. Each
        package builds the public surfaces and structured signals AI
        assistants and AI-assisted buyers read.
      </p>
      <ul className="mt-6 grid gap-4 sm:grid-cols-2" data-testid="ai-authority-packages">
        {[SNAPSHOT, SPRINT, BUILDOUT, RETAINER, SYSTEM].map((pkg) =>
          pkg ? (
            <li
              key={pkg.slug}
              className="flex h-full flex-col rounded-md border border-zinc-800 bg-zinc-900/40 p-5"
              data-testid={`pkg-card-${pkg.slug}`}
            >
              <p className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
                {packagePriceDisplay(pkg)} · {pkg.timeline}
              </p>
              <h3 className="mt-2 text-lg font-semibold tracking-tight text-zinc-100">
                {pkg.name}
              </h3>
              <p className="mt-2 text-sm text-zinc-300 leading-relaxed">
                {pkg.tagline}
              </p>
              <div className="mt-3 rounded border border-zinc-800 bg-zinc-950/50 p-3">
                <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                  Who it&rsquo;s for
                </p>
                <p className="mt-1 text-xs text-zinc-300 leading-relaxed">
                  {pkg.whoItsFor}
                </p>
              </div>
              <p className="mt-3 text-xs text-zinc-500 leading-relaxed">
                {pkg.positioning}
              </p>
              <ul className="mt-4 space-y-1.5 text-xs text-zinc-400">
                {pkg.deliverables.slice(0, 4).map((d) => (
                  <li key={d} className="flex gap-2">
                    <span aria-hidden className="mt-1 inline-block h-1 w-1 shrink-0 rounded-full bg-zinc-600" />
                    <span>{d}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex flex-wrap gap-2 pt-1">
                <Link
                  href="/ai-search-authority/score"
                  data-cta={`ai-pkg-${pkg.slug}-test`}
                  className="inline-block rounded-md border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-100 hover:bg-zinc-800"
                >
                  Take the AI Buyer Trust Test
                </Link>
                <CTA
                  label="Talk to ProofHook"
                  subject={`ProofHook — ${pkg.name} (${pkg.slug})`}
                  ctaId={`ai-pkg-${pkg.slug}-talk`}
                  className="inline-block rounded-md border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-100 hover:bg-zinc-800"
                />
              </div>
            </li>
          ) : null,
        )}
      </ul>

      {/* ── What happens after the test ────────────────────────────── */}
      <AfterTheTestSection />

      {/* ── Full commercial flow ───────────────────────────────────── */}
      <CommercialFlowSection />

      {/* ── FAQ ─────────────────────────────────────────────────────── */}
      <SectionHeading>Frequently asked questions</SectionHeading>
      <div className="mt-4 space-y-6">
        {FAQ.map((qa) => (
          <div key={qa.question}>
            <p className="font-medium text-zinc-100">{qa.question}</p>
            <p className="mt-1.5 text-zinc-400 leading-relaxed">{qa.answer}</p>
          </div>
        ))}
      </div>

      {/* ── Related reading ───────────────────────────────────────── */}
      <SectionHeading>Related reading</SectionHeading>
      <ul className="mt-4 grid gap-2 text-zinc-300 sm:grid-cols-2">
        <li>
          <Link href="/how-it-works" className="hover:text-zinc-100">
            How a ProofHook engagement works →
          </Link>
        </li>
        <li>
          <Link href="/answers/what-is-ai-search-authority" className="hover:text-zinc-100">
            What is AI search authority? →
          </Link>
        </li>
        <li>
          <Link href="/answers/how-to-make-a-company-ai-searchable" className="hover:text-zinc-100">
            How to make a company AI-searchable →
          </Link>
        </li>
        <li>
          <Link href="/proof" className="hover:text-zinc-100">
            What ProofHook actually ships →
          </Link>
        </li>
      </ul>

      <div className="mt-12">
        <CTA label="Talk to ProofHook" subject="ProofHook — AI Buyer Trust Infrastructure" ctaId="ai-search-authority-talk" />
      </div>
    </MarketingShell>
  );
}
