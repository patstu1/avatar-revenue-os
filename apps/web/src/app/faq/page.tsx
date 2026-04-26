import type { Metadata } from "next";

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

const PAGE_URL = "/faq";

const FAQ = [
  {
    question: "What is ProofHook?",
    answer:
      "ProofHook is a creative production and search-authority service for founder-led brands, SaaS, AI, and service businesses. We produce paid-media-ready short-form video creative and we make brands easier for search engines and AI systems to understand, categorize, cite, and recommend.",
  },
  {
    question: "What packages does ProofHook offer?",
    answer:
      "Signal Entry ($1,500), Momentum Engine ($2,500), Conversion Architecture ($3,500), Paid Media Engine ($4,500), Launch Sequence ($5,000), Creative Command ($7,500), and the AI Search Authority Sprint (from $4,500).",
  },
  {
    question: "Does ProofHook guarantee Google or AI search rankings?",
    answer:
      "No. We do not guarantee rankings, AI placements, citations in ChatGPT or Perplexity, AI Overview inclusion in Google, or Bing Copilot recommendations. Search and AI systems make their own decisions and change frequently. We improve the inputs those systems use — machine readability, entity authority, crawlability, and citation readiness — to increase your eligibility for search and AI discovery.",
  },
  {
    question: "How fast does ProofHook deliver?",
    answer:
      "Signal Entry runs in 7 days. Conversion Architecture, Launch Sequence, and the AI Search Authority Sprint run in 10–14 days. Momentum Engine, Paid Media Engine, and Creative Command are recurring monthly engagements.",
  },
  {
    question: "Who buys ProofHook?",
    answer:
      "Founder-led brands, SaaS companies, AI companies, service businesses, clinics, ecommerce brands, agencies, consultants, and premium local businesses that want short-form creative or search and AI authority work executed on a tight timeline.",
  },
  {
    question: "Where does ProofHook show up?",
    answer:
      "We do not control where AI search and recommendation systems will surface a brand. We strengthen the inputs (structured data, entity pages, internal linking, citation readiness) those systems read. The result is that your brand becomes easier to understand and surface across Google, ChatGPT Search, Bing Copilot, Perplexity, and adjacent answer engines.",
  },
  {
    question: "Can I see ProofHook's portfolio?",
    answer:
      "Yes — request a portfolio walkthrough at hello@proofhook.com. We share work with a relevant fit; we do not publish a public client list to protect operator-specific deal terms.",
  },
  {
    question: "How do I start?",
    answer:
      "Email hello@proofhook.com with the package you want and a short description of your business. We reply with a scoping call slot and an onboarding form.",
  },
];

export const metadata: Metadata = {
  title: "FAQ | ProofHook",
  description:
    "Frequently asked questions about ProofHook: packages, pricing, timelines, what we will and won't promise, and how to start.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function FaqPage() {
  return (
    <MarketingShell pageId="faq" breadcrumbs={[{ label: "Home", url: "/" }, { label: "FAQ", url: PAGE_URL }]}>
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <FaqJsonLd qa={FAQ} />

      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Frequently asked questions</h1>
        <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
          Short answers about ProofHook&apos;s packages, what we will and won&apos;t
          promise, and how engagements run.
        </p>
      </header>

      <div className="mt-10 space-y-8">
        {FAQ.map((qa) => (
          <div key={qa.question}>
            <h2 className="text-base font-medium text-zinc-100">{qa.question}</h2>
            <p className="mt-2 text-zinc-400 leading-relaxed">{qa.answer}</p>
          </div>
        ))}
      </div>

      <SectionHeading>What we won&apos;t promise</SectionHeading>
      <Bullets
        items={[
          "Guaranteed Google rankings",
          "Guaranteed AI Overview placement in Google",
          "Guaranteed citations in ChatGPT, Perplexity, Bing Copilot, or any other AI system",
          "Specific revenue, conversion, or click numbers tied to creative output",
        ]}
      />

      <div className="mt-12">
        <CTA label="Talk to ProofHook" subject="ProofHook — FAQ" />
      </div>
    </MarketingShell>
  );
}
