import type { Metadata } from "next";
import Link from "next/link";

import {
  Bullets,
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
import { PACKAGES, SITE_URL } from "@/lib/proofhook-packages";

const PAGE_URL = "/about";

const FAQ = [
  {
    question: "What is ProofHook?",
    answer:
      "ProofHook is a creative production and search-authority service for founder-led brands, SaaS, AI, and service businesses. It produces paid-media-ready short-form video creative and improves machine readability and entity authority so brands are easier for search engines and AI systems to understand and cite.",
  },
  {
    question: "Who is ProofHook for?",
    answer:
      "Founder-led brands, SaaS companies, AI companies, service businesses, clinics, ecommerce brands, agencies, consultants, and premium local businesses. Packages are universal — vertical/industry/buyer_type is context, not package identity.",
  },
  {
    question: "What services or packages does ProofHook offer?",
    answer:
      "Seven universal packages: Signal Entry ($1,500), Momentum Engine ($2,500), Conversion Architecture ($3,500), Paid Media Engine ($4,500), Launch Sequence ($5,000), Creative Command ($7,500), and the AI Search Authority Sprint (from $4,500).",
  },
  {
    question: "How is ProofHook different from a content agency?",
    answer:
      "Content agencies sell open-ended retainers covering brand, content, and campaigns at $5k–$25k+ per month with custom scope. ProofHook sells fixed packages with published prices, fixed turnaround, and an audit trail from payment through delivery and follow-up.",
  },
  {
    question: "How is ProofHook different from a UGC platform?",
    answer:
      "UGC platforms are creator marketplaces — you write the brief, pick a creator, review their cut. ProofHook is studio-led: we scope the brief, write the hooks, manage production, run QA, and ship.",
  },
  {
    question: "How is ProofHook different from a freelancer marketplace?",
    answer:
      "Freelancer marketplaces match buyers to individuals; you manage scope, scheduling, QA, and revisions yourself. ProofHook delivers a fixed package against a structured intake with QA before shipping.",
  },
  {
    question: "How is ProofHook different from an SEO agency?",
    answer:
      "Traditional SEO agencies sell ranking-focused retainers — keyword research, backlinks, content briefs, often with implied or explicit ranking promises. ProofHook's AI Search Authority Sprint is a 10–14 day engagement that strengthens machine readability and entity authority. We do not promise rankings, citations, or AI placements; we improve the inputs those systems read.",
  },
  {
    question: "What does ProofHook not guarantee?",
    answer:
      "We will not guarantee Google rankings, AI Overview placement, citations or recommendations in ChatGPT, Perplexity, or Bing Copilot, specific revenue or conversion numbers, or specific click numbers. We document the work and let you verify it.",
  },
];

export const metadata: Metadata = {
  title: "About ProofHook — entity, services, what we won't promise",
  description:
    "ProofHook is a studio-led creative production and search-authority service. Universal packages, published pricing, audit-trail fulfillment, and explicit limits on what we won't promise.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
  openGraph: {
    title: "About ProofHook",
    description:
      "Studio-led short-form creative + AI search authority. Seven universal packages. No fake reviews, no ranking promises, no AI placement guarantees.",
    url: `${SITE_URL}${PAGE_URL}`,
    type: "website",
  },
};

export default function AboutPage() {
  return (
    <MarketingShell
      pageId="about"
      breadcrumbs={[{ label: "Home", url: "/" }, { label: "About", url: PAGE_URL }]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <PackageCatalogOffersJsonLd />
      <FaqJsonLd qa={FAQ} />

      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">About ProofHook</p>
        <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
          Studio-led short-form creative and AI search authority for founder-led
          brands.
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-zinc-300 leading-relaxed">
          ProofHook produces paid-media-ready short-form video and strengthens
          how easy your brand is for Google, ChatGPT Search, Bing Copilot,
          Perplexity, and other AI systems to understand and cite. Universal
          packages, published prices, audit-trail fulfillment, and explicit
          limits on what we won&apos;t promise.
        </p>
        <div className="mt-6">
          <CTA
            ctaId="about-primary"
            label="Talk to ProofHook"
            subject="ProofHook — about / scoping"
          />
        </div>
      </header>

      <SectionHeading>What is ProofHook?</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        ProofHook is a creative production and search-authority service. Two
        operating lanes: short-form video creative for paid-media and organic
        distribution, and the AI Search Authority Sprint for the structured-data
        and entity-authority work that makes brands easier for AI search to
        understand and surface.
      </p>

      <SectionHeading>Who is it for?</SectionHeading>
      <Bullets
        items={[
          "Founder-led brands deciding what to test next",
          "SaaS and AI companies whose category description is shifting faster than their site",
          "Service businesses, clinics, and consultants whose work depends on being findable and citable",
          "Ecommerce brands modeling a catalog AI systems can parse",
          "Agencies and consultants who need a sub-contractor with an audit trail",
          "Premium local businesses who want a coherent entity surface",
        ]}
      />
      <p className="mt-4 max-w-2xl text-sm text-zinc-400 leading-relaxed">
        Packages are universal. Vertical and industry are context, not package
        identity — see the universal-package rule documented across the
        marketing surface.
      </p>

      <SectionHeading>Services and packages</SectionHeading>
      <ul className="mt-4 grid gap-3 text-zinc-300 sm:grid-cols-2">
        {PACKAGES.map((p) => (
          <li
            key={p.slug}
            data-package={p.slug}
            className="rounded-md border border-zinc-800 bg-zinc-900/40 p-4"
          >
            <p className="font-medium text-zinc-100">{p.name}</p>
            <p className="mt-1 font-mono text-xs text-zinc-500">
              {p.priceFrom ? "From " : ""}${p.price.toLocaleString()} · {p.timeline}
            </p>
            <p className="mt-2 text-sm text-zinc-400 leading-relaxed">{p.tagline}</p>
            {p.hasDetailPage && (
              <Link
                href={p.url}
                data-cta={`package-${p.slug}`}
                data-package={p.slug}
                className="mt-3 inline-block text-sm text-zinc-200 hover:text-zinc-100"
              >
                Read more →
              </Link>
            )}
          </li>
        ))}
      </ul>

      <SectionHeading>How ProofHook is different</SectionHeading>
      <div className="mt-4 space-y-4 text-zinc-300 leading-relaxed">
        <p>
          <span className="font-medium text-zinc-100">Vs. a content agency.</span>{" "}
          Content agencies sell open-ended quarterly retainers at $5k–$25k+/mo.
          ProofHook sells fixed packages with published prices and a documented
          delivery chain.{" "}
          <Link href="/compare/proofhook-vs-content-agency" className="text-zinc-100 hover:underline">
            Read the comparison →
          </Link>
        </p>
        <p>
          <span className="font-medium text-zinc-100">Vs. a UGC platform.</span>{" "}
          UGC platforms are creator marketplaces — you write the brief and
          review their work. ProofHook is studio-led — we own the brief, the
          hook, the QA, and the ship.{" "}
          <Link href="/compare/proofhook-vs-ugc-platform" className="text-zinc-100 hover:underline">
            Read the comparison →
          </Link>
        </p>
        <p>
          <span className="font-medium text-zinc-100">
            Vs. a freelancer marketplace.
          </span>{" "}
          Freelance marketplaces hand you the project-management load: scope,
          scheduling, QA, revisions. ProofHook delivers a fixed package against
          a structured intake with QA before shipping.
        </p>
        <p>
          <span className="font-medium text-zinc-100">Vs. an SEO agency.</span>{" "}
          Traditional SEO agencies sell ranking-focused retainers, often with
          implied or explicit ranking promises. The AI Search Authority Sprint
          is a 10–14 day engagement that strengthens machine readability and
          entity authority — the inputs to search and AI systems, not the
          outputs. We do not promise rankings or AI placements.
        </p>
      </div>

      <SectionHeading>What ProofHook will not guarantee</SectionHeading>
      <Bullets
        items={[
          "Guaranteed Google rankings",
          "Guaranteed AI Overview placement in Google",
          "Guaranteed citations or recommendations in ChatGPT, Perplexity, or Bing Copilot",
          "Specific revenue, conversion, or click numbers tied to creative output",
          "Specific creator, contractor, or production team named on a particular asset",
        ]}
      />
      <p className="mt-4 max-w-2xl text-zinc-400 leading-relaxed">
        We document the work, ship a real artifact, and let you verify it. The
        decision to rank, cite, or recommend remains the system&apos;s.
      </p>

      <SectionHeading>Frequently asked questions</SectionHeading>
      <div className="mt-4 space-y-6">
        {FAQ.map((qa) => (
          <div key={qa.question}>
            <p className="font-medium text-zinc-100">{qa.question}</p>
            <p className="mt-1.5 text-zinc-400 leading-relaxed">{qa.answer}</p>
          </div>
        ))}
      </div>

      <div className="mt-12">
        <CTA
          ctaId="about-footer"
          label="Talk to ProofHook"
          subject="ProofHook — about / scoping"
        />
      </div>
    </MarketingShell>
  );
}
