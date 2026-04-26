import type { Metadata } from "next";
import Link from "next/link";

import {
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

const PAGE_URL = "/answers/what-is-ai-search-authority";

const FAQ = [
  {
    question: "Is AI search authority the same as SEO?",
    answer:
      "Overlapping but not identical. SEO has historically been about ranking signals for traditional search results pages. AI search authority extends that into structured-data and entity-graph signals that AI search systems use when composing direct answers.",
  },
  {
    question: "Will improving AI search authority guarantee I get recommended by ChatGPT or Perplexity?",
    answer:
      "No. We do not guarantee recommendations or citations. AI search systems make their own decisions. We improve the inputs those systems read — structured data, entity authority, crawlability, citation readiness — to increase eligibility for surfacing.",
  },
  {
    question: "How do I measure AI search authority?",
    answer:
      "Indirectly, today. You can track AI-source referrers (chat.openai.com, perplexity.ai, copilot.microsoft.com) in your analytics, monitor branded queries in Search Console, and run periodic prompts against the major AI search systems to see how they describe you.",
  },
];

export const metadata: Metadata = {
  title: "What is AI search authority? | ProofHook",
  description:
    "AI search authority is how easy your brand is for search engines and AI search systems to understand, categorize, trust, cite, and recommend. Direct answer in three sentences.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function AnswerWhatIsAiSearchAuthorityPage() {
  return (
    <MarketingShell
      pageId="answers/what-is-ai-search-authority"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "Answers", url: "/answers" },
        { label: "What is AI search authority?", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <FaqJsonLd qa={FAQ} />

      <header>
        <h1 className="text-3xl font-semibold leading-tight tracking-tight">
          What is AI search authority?
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-zinc-200 leading-relaxed">
          AI search authority is how easy your brand is for search engines and
          AI search systems to understand, categorize, trust, cite, and
          recommend. It&apos;s the <em>inputs</em> — structured data, entity
          pages, internal linking, citation readiness — not the <em>outputs</em>{" "}
          (rankings, citations) which are decided by the systems themselves.
        </p>
      </header>

      <SectionHeading>Why the input/output distinction matters</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        ProofHook will not promise the outputs. We will not promise guaranteed
        rankings, guaranteed AI Overview placement, or guaranteed ChatGPT
        citations — vendors who do are either misinformed or selling something
        they can&apos;t deliver. The systems that decide rankings and citations
        change constantly and don&apos;t accept paid placements. What you can
        control is the input: how cleanly your site, structured data, entity
        authority, and citation surface present to those systems.
      </p>

      <SectionHeading>What &ldquo;authority&rdquo; means here</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Three components. <strong>Entity authority</strong>: a single canonical
        domain with consistent Organization / WebSite / Service / Product
        JSON-LD describing what you do.{" "}
        <strong>Citation readiness</strong>: pages structured so they&apos;re
        easy to extract and attribute (FAQPage, BreadcrumbList, clear H1/H2
        hierarchy).{" "}
        <strong>Crawler access</strong>: robots.txt that doesn&apos;t
        accidentally block the bots reading your content (Googlebot, Bingbot,
        OAI-SearchBot, GPTBot, PerplexityBot).
      </p>

      <SectionHeading>What ProofHook delivers</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        The{" "}
        <Link href="/ai-search-authority" className="text-zinc-100 hover:underline">
          AI Search Authority Sprint
        </Link>{" "}
        is a 10–14 day engagement that improves all three components. From
        $4,500. We document the work and let you verify it. We do not promise
        rankings or AI placements.
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
        <li><Link href="/answers/how-to-make-a-company-ai-searchable" className="hover:text-zinc-100">How to make a company AI searchable →</Link></li>
        <li><Link href="/answers/how-to-get-cited-by-ai-search-engines" className="hover:text-zinc-100">How to get cited by AI search engines →</Link></li>
        <li><Link href="/ai-search-authority" className="hover:text-zinc-100">AI Search Authority Sprint →</Link></li>
        <li><Link href="/faq" className="hover:text-zinc-100">FAQ →</Link></li>
      </ul>

      <div className="mt-12">
        <CTA ctaId="answers-cta" label="Talk to ProofHook" subject="ProofHook — AI search authority" />
      </div>
    </MarketingShell>
  );
}
