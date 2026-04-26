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

const PAGE_URL = "/industries/ai-startups";

export const metadata: Metadata = {
  title: "ProofHook for AI startups | ProofHook",
  description:
    "AI startups: improve machine readability and entity authority so search engines and AI search systems describe your product accurately.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function IndustryAiStartupsPage() {
  return (
    <MarketingShell
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "Industries", url: "/industries" },
        { label: "AI startups", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />

      <header>
        <h1 className="text-3xl font-semibold tracking-tight">
          ProofHook for AI startups
        </h1>
        <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
          AI products move faster than the description of them. Six months in,
          the model, the use case, and the pricing have all changed — and the
          way ChatGPT, Bing Copilot, Perplexity, and Google describe you is
          months out of date. ProofHook tightens that gap.
        </p>
      </header>

      <p className="mt-4 rounded-md border border-zinc-800 bg-zinc-900/40 px-4 py-3 text-sm text-zinc-400">
        The AI Search Authority Sprint and the rest of ProofHook&apos;s
        packages are not locked to any vertical. This page focuses on the AI
        startup angle; the same engagement runs unchanged for SaaS,
        ecommerce, clinics, agencies, consultants, premium local
        businesses, and founder-led brands.
      </p>

      <SectionHeading>Why this matters for AI startups</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Buyers research AI tools through other AI tools. If your entity
        authority is weak — no Organization or Service JSON-LD, no canonical
        comparison pages, no answer-engine content — the model will quote
        whoever is structured cleanest and most recently. We make your
        structured data, entity pages, and comparison content easier for those
        systems to parse and cite. We do not promise that any specific AI
        system will recommend you.
      </p>

      <SectionHeading>What we do for AI startups</SectionHeading>
      <Bullets
        items={[
          "Organization, WebSite, Service, and Product/Offer JSON-LD across the marketing surface",
          "Entity / about page that names what you do without marketing fluff",
          "FAQ and how-it-works pages tuned for answer-engine extraction",
          "Comparison pages against the obvious adjacent tools",
          "5 answer-engine content pages targeting buyer intents tied to your category",
          "robots.txt review — keep Googlebot, Bingbot, OAI-SearchBot, and GPTBot allowed unless you have a specific reason not to",
          "Internal linking map that consolidates entity authority on the right canonical URLs",
          "Search Console + Bing Webmaster Tools checklists",
          "AI referral tracking plan so you can see which AI tools sent traffic",
        ]}
      />

      <SectionHeading>What we won&apos;t promise</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        We will not guarantee that ChatGPT, Google AI Overviews, Bing Copilot,
        Perplexity, or any other system will mention your product. AI systems
        change frequently and make their own choices. We strengthen the inputs
        they read.
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
          <Link href="/how-it-works" className="hover:text-zinc-100">
            How it works →
          </Link>
        </li>
      </ul>

      <div className="mt-12">
        <CTA label="Start a sprint" subject="ProofHook — AI startup sprint" />
      </div>
    </MarketingShell>
  );
}
