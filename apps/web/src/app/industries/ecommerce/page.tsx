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

const PAGE_URL = "/industries/ecommerce";

export const metadata: Metadata = {
  title: "ProofHook for ecommerce | ProofHook",
  description:
    "Ecommerce brands: improve product / offer structured data and entity authority so search and AI systems can model your catalog accurately.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function IndustryEcommercePage() {
  return (
    <MarketingShell
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "Industries", url: "/industries" },
        { label: "Ecommerce", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />

      <header>
        <h1 className="text-3xl font-semibold tracking-tight">
          ProofHook for ecommerce
        </h1>
        <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
          Shoppers ask AI systems for product recommendations. If your products
          aren&apos;t modeled cleanly — Product, Offer, Brand, GTIN, price,
          availability — the AI system reaches for the catalog that is.
        </p>
      </header>

      <p className="mt-4 rounded-md border border-zinc-800 bg-zinc-900/40 px-4 py-3 text-sm text-zinc-400">
        ProofHook&apos;s packages are not locked to any vertical. This page
        focuses on the ecommerce angle; the same engagement runs unchanged for
        AI startups, SaaS, clinics, agencies, consultants, premium local
        businesses, and founder-led brands.
      </p>

      <SectionHeading>What we audit and fix</SectionHeading>
      <Bullets
        items={[
          "Product and Offer JSON-LD across the catalog or a representative slice",
          "Brand and Organization entity authority on the marketing surface",
          "Canonical URL hygiene across category, product, and variant pages",
          "robots.txt review — keep Googlebot, Bingbot, OAI-SearchBot, and GPTBot allowed unless you have a specific reason not to",
          "sitemap.xml that includes category, product, FAQ, comparison, and authority pages",
          "Internal linking map between hero products, comparison pages, and answer-engine content",
          "FAQ content that targets the buyer questions AI search surfaces",
          "Search Console + Bing Webmaster Tools checklists",
        ]}
      />

      <SectionHeading>What we don&apos;t do</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        We don&apos;t replace your shop platform, rewrite your catalog at scale,
        or re-platform your storefront. We work with what you have, layer in
        the entity authority and structured data, and document the gaps your
        team can close after we leave.
      </p>

      <SectionHeading>What we won&apos;t promise</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        We won&apos;t promise that Google AI Overviews, ChatGPT, Bing Copilot,
        or Perplexity will recommend your products. We will improve the inputs
        those systems use and document the work so you can verify it.
      </p>

      <SectionHeading>Related</SectionHeading>
      <ul className="mt-4 grid gap-2 text-zinc-300 sm:grid-cols-2">
        <li>
          <Link href="/ai-search-authority" className="hover:text-zinc-100">
            AI Search Authority Sprint →
          </Link>
        </li>
        <li>
          <Link href="/industries/saas" className="hover:text-zinc-100">
            For SaaS companies →
          </Link>
        </li>
        <li>
          <Link href="/compare/proofhook-vs-ugc-platform" className="hover:text-zinc-100">
            ProofHook vs. a UGC platform →
          </Link>
        </li>
      </ul>

      <div className="mt-12">
        <CTA label="Start a sprint" subject="ProofHook — ecommerce sprint" />
      </div>
    </MarketingShell>
  );
}
