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
  WebSiteJsonLd,
} from "@/components/jsonld";
import { SITE_URL } from "@/lib/proofhook-packages";

const PAGE_URL = "/answers/how-to-make-a-company-ai-searchable";

const FAQ = [
  {
    question: "Will doing this guarantee that ChatGPT or Perplexity recommend my company?",
    answer:
      "No. AI search systems make their own decisions and change frequently. What you can do is improve the inputs they use — structured data, entity authority, crawlability, citation readiness — to increase your eligibility for surfacing.",
  },
  {
    question: "Do I need to allow GPTBot and OAI-SearchBot?",
    answer:
      "Only if you want to be eligible for ChatGPT Search and OpenAI's web crawl. Blocking them is a defensible choice (data-rights, privacy) but it removes you from the index those systems read.",
  },
  {
    question: "What's the fastest meaningful change?",
    answer:
      "Add Organization, WebSite, Service, and Product/Offer JSON-LD on a single canonical domain, and make sure robots.txt isn't blocking the four big bots (Googlebot, Bingbot, OAI-SearchBot, GPTBot).",
  },
];

export const metadata: Metadata = {
  title: "How to make a company AI searchable | ProofHook",
  description:
    "Three layers: structured data, crawler access, answer-engine content. Direct answer with the checklist.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function AnswerHowToMakeAiSearchablePage() {
  return (
    <MarketingShell
      pageId="answers/how-to-make-a-company-ai-searchable"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "Answers", url: "/answers" },
        { label: "How to make a company AI searchable", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <FaqJsonLd qa={FAQ} />

      <header>
        <h1 className="text-3xl font-semibold leading-tight tracking-tight">
          How to make a company AI searchable
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-zinc-200 leading-relaxed">
          Three layers. <strong>Entity authority</strong>: clean Organization,
          WebSite, Service, and Product/Offer JSON-LD on a single canonical
          domain. <strong>Crawler access</strong>: a robots.txt that allows
          Googlebot, Bingbot, OAI-SearchBot, and GPTBot unless you have a
          deliberate reason not to. <strong>Answer-engine content</strong>:
          pages that directly answer the question a buyer will ask, with FAQ
          and BreadcrumbList schema.
        </p>
      </header>

      <SectionHeading>The checklist</SectionHeading>
      <Bullets
        items={[
          "Decide a single canonical domain. Consolidate all entity authority on it.",
          "Add Organization JSON-LD on every public page.",
          "Add WebSite JSON-LD with sitelink searchbox where appropriate.",
          "Add Service JSON-LD for each service or package, linked back to the Organization @id.",
          "Add Product / Offer JSON-LD for purchasable units with current price + availability.",
          "Add FAQPage JSON-LD on pages with question/answer content.",
          "Add BreadcrumbList JSON-LD on every page deeper than the home.",
          "Audit robots.txt — keep Googlebot, Bingbot, OAI-SearchBot, GPTBot allowed.",
          "Publish a sitemap.xml with every public marketing surface.",
          "Build canonical URLs for entity, FAQ, how-it-works, comparison, industry-context, and answer-engine pages — and link them internally.",
          "Submit the sitemap to Google Search Console and Bing Webmaster Tools.",
          "Track AI referrals — referrers like chat.openai.com, perplexity.ai, copilot.microsoft.com.",
        ]}
      />

      <SectionHeading>Why this matters</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        AI search systems compose answers from sources they can parse, trust,
        and attribute. If your structured data is missing, your robots.txt is
        accidentally hostile, or your site has no canonical answer page for
        the question being asked, the system reaches for whoever is structured
        cleanest. That&apos;s often a competitor.
      </p>

      <SectionHeading>What ProofHook delivers</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        The{" "}
        <Link href="/ai-search-authority" className="text-zinc-100 hover:underline">
          AI Search Authority Sprint
        </Link>{" "}
        is a 10–14 day engagement that does this checklist on your site. From
        $4,500. We do not promise rankings or AI placements; we improve the
        inputs those systems read.
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

      <SectionHeading>Related</SectionHeading>
      <ul className="mt-4 grid gap-2 text-zinc-300 sm:grid-cols-2">
        <li><Link href="/answers/what-is-ai-search-authority" className="hover:text-zinc-100">What is AI search authority? →</Link></li>
        <li><Link href="/answers/how-to-get-cited-by-ai-search-engines" className="hover:text-zinc-100">How to get cited by AI search engines →</Link></li>
        <li><Link href="/ai-search-authority" className="hover:text-zinc-100">AI Search Authority Sprint →</Link></li>
        <li><Link href="/faq" className="hover:text-zinc-100">FAQ →</Link></li>
      </ul>

      <div className="mt-12">
        <CTA ctaId="answers-cta" label="Start a sprint" subject="ProofHook — make us AI-searchable" />
      </div>
    </MarketingShell>
  );
}
