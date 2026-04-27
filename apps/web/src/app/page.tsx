import type { Metadata } from "next";
import Link from "next/link";

import { HomepageTestCTA } from "@/components/ai-buyer-trust/HomepageTestCTA";
import {
  AfterTheTestSection,
  BuyerPsychologySection,
  CommercialFlowSection,
  DecisionLayerSection,
  HowItWorksSection,
  ResultToPackageSection,
  ScatteredToStructuredSection,
  ThirdShiftSection,
  WhatProofHookBuildsSection,
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
  WebSiteJsonLd,
} from "@/components/jsonld";
import {
  ORG,
  PACKAGE_BY_SLUG,
  SITE_URL,
  packagePriceDisplay,
  type ProofHookPackage,
} from "@/lib/proofhook-packages";

const PAGE_URL = "/";

const CREATIVE_PROOF_SLUGS = [
  "signal_entry",
  "momentum_engine",
  "conversion_architecture",
  "paid_media_engine",
  "launch_sequence",
  "creative_command",
] as const;

const AI_AUTHORITY_SLUGS = [
  "ai_search_authority_snapshot",
  "ai_search_authority_sprint",
  "proof_infrastructure_buildout",
  "authority_monitoring_retainer",
  "ai_search_authority_system",
] as const;

const FAQ = [
  {
    question: "Is ProofHook a creative agency or an AI authority service?",
    answer:
      "Both. ProofHook builds the proof, hooks, pages, and trust signals businesses need to be understood, trusted, and chosen in the AI decision era. Creative Proof packages handle short-form, founder, paid social, and proof-video work. AI Authority packages handle entity surfaces, FAQs, comparisons, schema, and the structured signals AI assistants read.",
  },
  {
    question: "Where do the two lanes connect?",
    answer:
      "The AI Buyer Trust Test scores public website signals across both lanes. When proof or offer clarity reads as a creative-side gap, the test recommends a Creative Proof companion alongside the AI Authority package — so the new authority surfaces ship with the proof videos and hook variants that fill them.",
  },
  {
    question: "What does the AI Buyer Trust Test check?",
    answer:
      "Eight buyer-language dimensions plus three technical signals: what your business does, who you serve, how clearly your offers are explained, how your proof is structured, whether buyer questions are answered, whether comparison signals exist, whether schema and crawlability support machine readability, and whether trust signals are easy to find.",
  },
  {
    question: "How does ProofHook fit the AI decision layer?",
    answer:
      "ProofHook structures the public signals AI systems and AI-assisted buyers read when they evaluate a business. Clear inputs lead to clearer recommendations. The Sprint, Buildout, and Retainer build, refresh, and monitor those inputs over time.",
  },
  {
    question: "What happens after the test?",
    answer:
      "An instant ProofHook Authority Score with top trust gaps, buyer questions, a quick win, and a recommended next step. Request the reviewed Authority Snapshot and a ProofHook operator delivers the full per-dimension diagnostic plus a written proposal for the recommended package.",
  },
  {
    question: "What does it cost to start?",
    answer:
      "The AI Buyer Trust Test is free. The reviewed Authority Snapshot is free with email for founding clients. From there, packages start at $1,500 (UGC Starter Pack on the creative side, AI Search Authority Sprint on the authority side) and scale up to custom System engagements.",
  },
  {
    question: "How is this different from a generic AI SEO or GEO tool?",
    answer:
      "Generic AI SEO and GEO tools track citations and visibility from the outside. ProofHook builds the AI Buyer Trust Infrastructure those systems read — public proof, offers, FAQs, comparisons, schema, and trust structure — and pairs it with the creative proof that fills those surfaces.",
  },
];

export const metadata: Metadata = {
  title: `${ORG.name} — Creative Proof + AI Buyer Trust Infrastructure`,
  description:
    "ProofHook builds the proof, hooks, pages, and trust signals businesses need to be understood, trusted, and chosen in the AI decision era. Short-form creative for paid social, plus AI Buyer Trust Infrastructure for the AI decision layer. Take the free AI Buyer Trust Test.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
  openGraph: {
    title: `${ORG.name} — Creative Proof + AI Buyer Trust Infrastructure`,
    description:
      "Google helped customers find businesses. AI is helping them decide who to trust. ProofHook builds the creative, proof, and authority infrastructure that wins both.",
    url: `${SITE_URL}${PAGE_URL}`,
    type: "website",
  },
};

function PackageCard({ pkg, ctaId }: { pkg: ProofHookPackage; ctaId: string }) {
  return (
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
      <p className="mt-2 text-sm text-zinc-300 leading-relaxed">{pkg.tagline}</p>
      <div className="mt-3 rounded border border-zinc-800 bg-zinc-950/50 p-3">
        <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
          Who it&rsquo;s for
        </p>
        <p className="mt-1 text-xs text-zinc-300 leading-relaxed">
          {pkg.whoItsFor}
        </p>
      </div>
      <div className="mt-4 flex flex-wrap gap-2 pt-1">
        {pkg.lane === "ai_authority" ? (
          <Link
            href="/ai-search-authority/score"
            data-cta={ctaId}
            className="inline-block rounded-md border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-100 hover:bg-zinc-800"
          >
            Take the AI Buyer Trust Test
          </Link>
        ) : (
          <CTA
            label="Talk to ProofHook"
            subject={`ProofHook — ${pkg.name} (${pkg.slug})`}
            ctaId={ctaId}
            className="inline-block rounded-md border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-100 hover:bg-zinc-800"
          />
        )}
      </div>
    </li>
  );
}

export default function HomePage() {
  return (
    <MarketingShell pageId="home">
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <PackageCatalogOffersJsonLd />
      <FaqJsonLd qa={FAQ} />

      {/* ── Hero — 5-second comprehension ──────────────────────────── */}
      <section data-testid="home-hero">
        <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
          Creative Proof + AI Buyer Trust Infrastructure
        </p>
        <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-tight text-zinc-100 sm:text-4xl">
          Become the business AI assistants and buyers can understand,
          compare, and choose.
        </h1>
        <p className="mt-5 max-w-3xl text-lg text-zinc-200 leading-relaxed">
          ProofHook builds the proof, pages, hooks, and authority structure
          that founder-led brands, SaaS, AI, and service businesses need to
          win in paid social, in search, and in the AI systems helping
          buyers decide.
        </p>
        <p className="mt-4 max-w-3xl text-zinc-300 leading-relaxed">
          Take the free AI Buyer Trust Test. Get a ProofHook Authority Score,
          your top trust gaps, buyer questions you should be answering, a
          quick win, and a recommended package.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/ai-search-authority/score"
            data-cta="hero-trust-test"
            className="inline-block rounded-md border border-zinc-100 bg-zinc-100 px-5 py-2.5 text-sm font-medium text-zinc-950 hover:bg-zinc-200"
          >
            Take the free AI Buyer Trust Test
          </Link>
          <a
            href="#packages"
            data-cta="hero-packages-anchor"
            className="inline-block rounded-md border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-200 hover:bg-zinc-900"
          >
            See packages
          </a>
        </div>
        <p className="mt-4 max-w-3xl text-sm text-zinc-400 leading-relaxed">
          Founding-client launch pricing. Authority Snapshot is free with
          email.
        </p>
      </section>

      {/* ── How ProofHook works — 4 steps ──────────────────────────── */}
      <HowItWorksSection />

      {/* ── Buyer psychology — why this matters now ────────────────── */}
      <BuyerPsychologySection />

      {/* ── What ProofHook builds — both lanes spelled out ─────────── */}
      <WhatProofHookBuildsSection />

      {/* ── Result to package mapping — score band → recommended build */}
      <ResultToPackageSection />

      {/* ── Packages — dual-lane grid with whoItsFor + price + CTA ── */}
      <section
        id="packages"
        data-testid="home-packages-section"
        className="mt-16 scroll-mt-24"
      >
        <SectionHeading>Packages</SectionHeading>
        <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
          Two connected lanes. Pick the one that matches the gap your
          Authority Score reveals — or talk to ProofHook about the right
          combination.
        </p>

        {/* AI Authority lane */}
        <div
          id="ai-authority"
          className="mt-10 scroll-mt-24"
          data-testid="home-ai-authority-section"
        >
          <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
            AI Authority Packages
          </p>
          <h3 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-100">
            Build the AI Buyer Trust Infrastructure that AI assistants read.
          </h3>
          <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
            Entity surfaces, offer clarity, FAQ architecture, comparison
            surfaces, schema, proof pages, and the trust signals AI-assisted
            buyers verify before they shortlist a business.
          </p>
          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-start">
            <ul className="grid gap-4 sm:grid-cols-2">
              {AI_AUTHORITY_SLUGS.map((slug) => {
                const pkg = PACKAGE_BY_SLUG[slug];
                if (!pkg) return null;
                return (
                  <PackageCard
                    key={pkg.slug}
                    pkg={pkg}
                    ctaId={`home-ai-${pkg.slug}`}
                  />
                );
              })}
            </ul>
            <div className="lg:sticky lg:top-6">
              <HomepageTestCTA />
            </div>
          </div>
        </div>

        {/* Creative Proof lane */}
        <div
          id="creative-proof"
          className="mt-12 scroll-mt-24"
          data-testid="home-creative-section"
        >
          <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
            Creative Proof Packages
          </p>
          <h3 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-100">
            Short-form creative that fills the surfaces and converts paid
            traffic.
          </h3>
          <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
            Hook-led short-form videos, founder clips, paid-social creative,
            UGC-style assets, and proof-video packs — built for paid media,
            not for vanity reach.
          </p>
          <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CREATIVE_PROOF_SLUGS.map((slug) => {
              const pkg = PACKAGE_BY_SLUG[slug];
              if (!pkg) return null;
              return (
                <PackageCard
                  key={pkg.slug}
                  pkg={pkg}
                  ctaId={`home-creative-${pkg.slug}`}
                />
              );
            })}
          </ul>
        </div>
      </section>

      {/* ── What happens after the test — buildable next steps ─────── */}
      <AfterTheTestSection />

      {/* ── Full commercial flow — Test → Snapshot → Package → ... ── */}
      <CommercialFlowSection />

      {/* ── Strategic explainer ─────────────────────────────────────── */}
      <ThirdShiftSection />
      <DecisionLayerSection />
      <ScatteredToStructuredSection />

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

      {/* ── Final CTA ───────────────────────────────────────────────── */}
      <SectionHeading>One operator team. Two connected lanes.</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Take the free AI Buyer Trust Test to see where your business stands
        in the AI decision layer, or talk to ProofHook about a creative or
        authority engagement.
      </p>
      <div className="mt-5 flex flex-wrap gap-3">
        <Link
          href="/ai-search-authority/score"
          data-cta="home-final-trust-test"
          className="inline-block rounded-md border border-zinc-100 bg-zinc-100 px-5 py-2.5 text-sm font-medium text-zinc-950 hover:bg-zinc-200"
        >
          Take the free AI Buyer Trust Test
        </Link>
        <CTA
          label="Talk to ProofHook"
          subject="ProofHook — Creative Proof + AI Buyer Trust"
          ctaId="home-final-talk"
        />
      </div>
    </MarketingShell>
  );
}
