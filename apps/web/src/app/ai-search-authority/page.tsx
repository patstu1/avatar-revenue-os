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
  ServiceJsonLd,
  WebSiteJsonLd,
} from "@/components/jsonld";
import { PACKAGE_BY_SLUG, SITE_URL } from "@/lib/proofhook-packages";

const PKG = PACKAGE_BY_SLUG["ai_search_authority_sprint"];
const PAGE_URL = "/ai-search-authority";

const FAQ = [
  {
    question: "Will ProofHook guarantee that ChatGPT, Google AI Overviews, Bing Copilot, or Perplexity recommend my company?",
    answer:
      "No. We do not promise rankings, citations, or AI placements. We improve the inputs those systems use — machine readability, entity authority, crawlability, and citation readiness — to increase your eligibility for search and AI discovery.",
  },
  {
    question: "What does the AI Search Authority Sprint include?",
    answer:
      "An AI search and entity audit, a robots.txt and crawler access review, sitemap and canonical URL review, structured data (Organization, WebSite, Service, Product/Offer, FAQPage, BreadcrumbList) implementation plan and assets, an about / entity page, FAQ, how-it-works, two industry pages, two comparison pages, five answer-engine content pages, an internal linking map, Google Search Console and Bing Webmaster Tools checklists, an AI referral tracking plan, and an external citation / backlink target checklist.",
  },
  {
    question: "How long does the engagement take?",
    answer: "10–14 days from kickoff.",
  },
  {
    question: "What does it cost?",
    answer:
      "From $4,500. Final scope and price depend on the size of your existing site, the number of products or services to model, and the depth of structured data and content build-out.",
  },
  {
    question: "Who is this for?",
    answer:
      "Founder-led brands, SaaS companies, AI companies, service businesses, clinics, ecommerce brands, agencies, consultants, and premium local businesses that want their brand to be easier to understand, categorize, trust, cite, and recommend.",
  },
  {
    question: "Will my robots.txt block AI crawlers?",
    answer:
      "Only if you choose to. By default we keep Googlebot, Bingbot, OAI-SearchBot, and GPTBot allowed so your content remains eligible for AI search and recommendation systems. We document trade-offs and let you decide.",
  },
];

export const metadata: Metadata = {
  title: `${PKG.name} — ${PKG.tagline} | ProofHook`,
  description: PKG.positioning,
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
  openGraph: {
    title: `${PKG.name} | ProofHook`,
    description: PKG.positioning,
    url: `${SITE_URL}${PAGE_URL}`,
    type: "website",
  },
};

export default function AiSearchAuthorityPage() {
  return (
    <MarketingShell breadcrumbs={[{ label: "Home", url: "/" }, { label: PKG.name, url: PAGE_URL }]}>
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <ServiceJsonLd pkg={PKG} pageUrl={PAGE_URL} />
      <PackageCatalogOffersJsonLd />
      <FaqJsonLd qa={FAQ} />

      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
          AI Search Authority Sprint
        </p>
        <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
          Make your company easier for search engines and AI systems to understand,
          categorize, trust, cite, and recommend.
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-zinc-300 leading-relaxed">
          {PKG.positioning}
        </p>
        <p className="mt-5 font-mono text-sm text-zinc-400">
          From <span className="text-zinc-100">${PKG.price.toLocaleString()}</span>
          {" · "}
          {PKG.timeline}
        </p>
        <div className="mt-6">
          <CTA
            label="Start an AI Search Authority Sprint"
            subject="ProofHook — AI Search Authority Sprint"
          />
        </div>
      </header>

      <SectionHeading>What it does</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        We strengthen the signals that search engines and AI search systems use
        when they decide whether your brand is the right answer to a buyer&apos;s
        question. We improve machine readability, strengthen entity authority,
        and increase eligibility for search and AI discovery — without making
        promises we can&apos;t verify.
      </p>

      <SectionHeading>What you get</SectionHeading>
      <Bullets items={PKG.deliverables} />

      <SectionHeading>What we won&apos;t promise</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        We will not promise that ChatGPT, Google AI Overviews, Bing Copilot,
        Perplexity, or any other system will rank, cite, or recommend you. Those
        systems make their own decisions and change frequently. What we will do
        is fix the inputs those systems use — and document them so you can
        verify the work and audit it later.
      </p>

      <SectionHeading>Who it&apos;s for</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Founder-led brands, SaaS companies, AI companies, service businesses,
        clinics, ecommerce brands, agencies, consultants, and premium local
        businesses. If you sell something specific and want to be findable,
        understandable, and citable to both humans and machines, this is for
        you.
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

      <SectionHeading>Related reading</SectionHeading>
      <ul className="mt-4 grid gap-2 text-zinc-300 sm:grid-cols-2">
        <li>
          <Link href="/how-it-works" className="hover:text-zinc-100">
            How a ProofHook engagement works →
          </Link>
        </li>
        <li>
          <Link href="/compare/proofhook-vs-content-agency" className="hover:text-zinc-100">
            ProofHook vs. a content agency →
          </Link>
        </li>
        <li>
          <Link href="/compare/proofhook-vs-ugc-platform" className="hover:text-zinc-100">
            ProofHook vs. a UGC platform →
          </Link>
        </li>
        <li>
          <Link href="/industries/ai-startups" className="hover:text-zinc-100">
            For AI startups →
          </Link>
        </li>
        <li>
          <Link href="/industries/saas" className="hover:text-zinc-100">
            For SaaS →
          </Link>
        </li>
        <li>
          <Link href="/industries/ecommerce" className="hover:text-zinc-100">
            For ecommerce →
          </Link>
        </li>
      </ul>

      <div className="mt-12">
        <CTA label="Talk to ProofHook" subject="ProofHook — AI Search Authority Sprint" />
      </div>
    </MarketingShell>
  );
}
