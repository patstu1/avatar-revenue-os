import type { Metadata } from "next";
import Link from "next/link";

import {
  Bullets,
  CTA,
  MarketingShell,
  SectionHeading,
} from "@/components/marketing-shell";
import {
  OrganizationJsonLd,
  WebSiteJsonLd,
} from "@/components/jsonld";
import { SITE_URL } from "@/lib/proofhook-packages";

const PAGE_URL = "/industries/saas";

export const metadata: Metadata = {
  title: "ProofHook for SaaS | ProofHook",
  description:
    "SaaS companies: strengthen entity authority and citation readiness so search and AI systems describe your product accurately for your buyers.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function IndustrySaasPage() {
  return (
    <MarketingShell
      pageId="industries/saas"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "Industries", url: "/industries" },
        { label: "SaaS", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />

      <header>
        <h1 className="text-3xl font-semibold tracking-tight">
          ProofHook for SaaS
        </h1>
        <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
          SaaS buyers compare three to five tools before they pick one. Most of
          that comparison is now mediated by search and AI systems. If your
          entity authority is weak, your competitor&apos;s positioning becomes
          the default description of your category.
        </p>
      </header>

      <p className="mt-4 rounded-md border border-zinc-800 bg-zinc-900/40 px-4 py-3 text-sm text-zinc-400">
        ProofHook&apos;s packages are not locked to any vertical. This page
        focuses on the SaaS angle; the same engagement runs unchanged for AI
        startups, ecommerce, clinics, agencies, consultants, premium local
        businesses, and founder-led brands.
      </p>

      <SectionHeading>Where SaaS companies usually leak</SectionHeading>
      <Bullets
        items={[
          "Pricing and packaging that aren't represented in structured data, so AI systems guess",
          "Comparison pages that exist but aren't linked from the canonical Service page",
          "FAQ content that lives in a help center the marketing crawlers don't fully index",
          "robots.txt that blocks AI crawlers as a side effect of a privacy or scraping fight",
          "An About page that lists team without ever naming the entity / product clearly",
        ]}
      />

      <SectionHeading>What ProofHook fixes</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        We strengthen the signals AI and search systems use to model your
        product: Organization / WebSite / Service / Product / Offer / FAQPage /
        BreadcrumbList JSON-LD, an entity page, an FAQ page, a how-it-works
        page, two industry pages, two comparison pages, five answer-engine
        content pages, and an internal linking map that consolidates authority
        on canonical URLs.
      </p>

      <SectionHeading>What we won&apos;t promise</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Guaranteed Google rankings, guaranteed AI Overview placement, or
        guaranteed citations in ChatGPT, Bing Copilot, or Perplexity are not on
        offer. We make your brand easier to understand and surface — the
        decision to surface remains the system&apos;s.
      </p>

      <SectionHeading>Related</SectionHeading>
      <ul className="mt-4 grid gap-2 text-zinc-300 sm:grid-cols-2">
        <li>
          <Link href="/ai-search-authority" className="hover:text-zinc-100">
            AI Search Authority Sprint →
          </Link>
        </li>
        <li>
          <Link href="/industries/ai-startups" className="hover:text-zinc-100">
            For AI startups →
          </Link>
        </li>
        <li>
          <Link href="/compare/proofhook-vs-content-agency" className="hover:text-zinc-100">
            ProofHook vs. a content agency →
          </Link>
        </li>
      </ul>

      <div className="mt-12">
        <CTA label="Start a sprint" subject="ProofHook — SaaS sprint" />
      </div>
    </MarketingShell>
  );
}
