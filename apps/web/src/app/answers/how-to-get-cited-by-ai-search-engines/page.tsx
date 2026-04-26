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

const PAGE_URL = "/answers/how-to-get-cited-by-ai-search-engines";

const FAQ = [
  {
    question: "Is there a way to pay for AI citations?",
    answer:
      "Not directly. Major AI search systems (ChatGPT Search, Google AI Overviews, Bing Copilot, Perplexity) do not sell citation slots. Anyone selling 'guaranteed AI placement' is selling something they can't deliver.",
  },
  {
    question: "How long does it take to see citations?",
    answer:
      "Variable and not guaranteed. Some pages get picked up within days; others take months; others never get cited. AI systems weight recency, source authority, and answer fit differently per query.",
  },
  {
    question: "Can ProofHook get me cited?",
    answer:
      "No. We can improve your eligibility — clean structured data, entity pages on a canonical domain, content that directly answers the buyer's question, internal linking that consolidates authority. The decision to cite remains the AI system's.",
  },
];

export const metadata: Metadata = {
  title: "How to get cited by AI search engines | ProofHook",
  description:
    "You can't guarantee a citation. You can improve eligibility: clean structured data, entity pages, direct-answer content, and external citations from trusted sources. Direct answer in three sentences.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function AnswerHowToGetCitedPage() {
  return (
    <MarketingShell
      pageId="answers/how-to-get-cited-by-ai-search-engines"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "Answers", url: "/answers" },
        { label: "How to get cited by AI search engines", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <FaqJsonLd qa={FAQ} />

      <header>
        <h1 className="text-3xl font-semibold leading-tight tracking-tight">
          How to get cited by AI search engines
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-zinc-200 leading-relaxed">
          You can&apos;t guarantee a citation — anyone who promises one is
          selling something they can&apos;t deliver. You can improve your
          eligibility: clean structured data on a single canonical domain,
          entity pages that name what you do, content that directly answers
          the question being asked, and external citations from sources the AI
          system already trusts.
        </p>
      </header>

      <SectionHeading>The four eligibility levers</SectionHeading>
      <div className="mt-4 space-y-5 text-zinc-300 leading-relaxed">
        <div>
          <p className="font-medium text-zinc-100">1. Structured data</p>
          <p className="mt-1.5 text-zinc-400">
            Organization, WebSite, Service, Product/Offer, FAQPage,
            BreadcrumbList JSON-LD on every public marketing page. Single
            canonical domain. Consistent <code>@id</code> values. AI systems
            that crawl your site read this first.
          </p>
        </div>
        <div>
          <p className="font-medium text-zinc-100">2. Entity authority</p>
          <p className="mt-1.5 text-zinc-400">
            A canonical About / entity page that names what you do without
            marketing fluff. An FAQ page that answers buyer questions
            directly. Comparison pages against the obvious adjacent options.
            Internal linking that consolidates authority on canonical URLs.
          </p>
        </div>
        <div>
          <p className="font-medium text-zinc-100">3. Direct-answer content</p>
          <p className="mt-1.5 text-zinc-400">
            Pages that answer specific buyer questions in the first 2–3
            sentences, with clean H1/H2 structure and FAQPage schema. AI
            systems extract the direct answer; if your page buries it in
            marketing copy, the system reaches for someone else&apos;s.
          </p>
        </div>
        <div>
          <p className="font-medium text-zinc-100">4. External citations</p>
          <p className="mt-1.5 text-zinc-400">
            Mentions and links from sources the AI system already trusts —
            industry publications, partner sites, podcast appearances,
            structured directory listings. ProofHook can hand you a checklist
            of citation targets; doing the outreach is your part.
          </p>
        </div>
      </div>

      <SectionHeading>What we won&apos;t promise</SectionHeading>
      <Bullets
        items={[
          "We will not promise citation slots — major AI systems don't sell them",
          "We will not promise specific timing — AI systems weight recency and source authority differently per query",
          "We will not promise that any particular AI system will mention your brand",
          "We will not invent backlinks, fake reviews, or fabricated case studies to engineer citations",
        ]}
      />

      <SectionHeading>What ProofHook delivers</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        The{" "}
        <Link href="/ai-search-authority" className="text-zinc-100 hover:underline">
          AI Search Authority Sprint
        </Link>{" "}
        delivers structured data, entity pages, direct-answer content, and an
        external citation / backlink target checklist. Plus a Search Console
        and Bing Webmaster Tools setup checklist and an AI referral tracking
        plan. From $4,500, 10–14 days.
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
        <li><Link href="/answers/how-to-make-a-company-ai-searchable" className="hover:text-zinc-100">How to make a company AI searchable →</Link></li>
        <li><Link href="/ai-search-authority" className="hover:text-zinc-100">AI Search Authority Sprint →</Link></li>
        <li><Link href="/faq" className="hover:text-zinc-100">FAQ →</Link></li>
      </ul>

      <div className="mt-12">
        <CTA ctaId="answers-cta" label="Talk to ProofHook" subject="ProofHook — AI citation eligibility" />
      </div>
    </MarketingShell>
  );
}
