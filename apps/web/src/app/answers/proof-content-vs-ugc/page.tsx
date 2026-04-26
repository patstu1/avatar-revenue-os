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

const PAGE_URL = "/answers/proof-content-vs-ugc";

const FAQ = [
  {
    question: "Is one better than the other?",
    answer:
      "Different tools for different jobs. UGC is the right tool when you need volume and trust comes from the creator. Proof-based content is the right tool when the buyer needs something to check before they spend.",
  },
  {
    question: "Can I use both?",
    answer:
      "Yes. Many brands run UGC for top-of-funnel volume and proof-based content for paid acquisition where claim-quality matters.",
  },
  {
    question: "Does ProofHook offer UGC?",
    answer:
      "No. ProofHook is studio-led, not a creator marketplace. We scope, write, produce, and QA every asset.",
  },
];

const TABLE = [
  {
    dimension: "Operating model",
    proof: "Studio-led. Brief, hook, production, QA owned by the studio.",
    ugc: "Marketplace. You write the brief; a creator picks it up.",
  },
  {
    dimension: "Brief depth",
    proof: "Structured intake feeds hook strategy and offer alignment.",
    ugc: "Creator-fillable; quality varies by who picks it up.",
  },
  {
    dimension: "Hook strategy",
    proof: "Multiple hooks per asset, anchored on verifiable claims.",
    ugc: "Creator chooses; volume tends to dominate angle quality.",
  },
  {
    dimension: "Best for",
    proof: "Paid-media acquisition, claim-heavy categories, B2B, premium DTC.",
    ugc: "Top-of-funnel volume, social proof, lifestyle categories.",
  },
  {
    dimension: "Audit trail",
    proof: "Operator-visible payment → intake → production → QA → delivery → followup.",
    ugc: "Platform messaging + creator deliverables. Varies by platform.",
  },
];

export const metadata: Metadata = {
  title: "Proof-based content vs. UGC | ProofHook",
  description:
    "Different operating models. Proof-based content is studio-led short-form built on verifiable claims. UGC is creator-marketplace short-form. Direct comparison in this answer.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function AnswerProofVsUgcPage() {
  return (
    <MarketingShell
      pageId="answers/proof-content-vs-ugc"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "Answers", url: "/answers" },
        { label: "Proof content vs. UGC", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <FaqJsonLd qa={FAQ} />

      <header>
        <h1 className="text-3xl font-semibold leading-tight tracking-tight">
          Proof-based content vs. UGC
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-zinc-200 leading-relaxed">
          Different operating models for different stages of growth. UGC is
          creator-marketplace short-form built on personality and lifestyle.
          Proof-based content is studio-led short-form built on verifiable
          claims, hook strategy, and offer alignment.
        </p>
      </header>

      <SectionHeading>Side-by-side</SectionHeading>
      <div className="mt-4 overflow-hidden rounded-lg border border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900 text-zinc-300">
            <tr>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">Dimension</th>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">Proof-based content</th>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">UGC</th>
            </tr>
          </thead>
          <tbody className="text-zinc-300">
            {TABLE.map((r) => (
              <tr key={r.dimension} className="align-top">
                <td className="border-b border-zinc-800 px-4 py-3 font-medium text-zinc-100">{r.dimension}</td>
                <td className="border-b border-zinc-800 px-4 py-3">{r.proof}</td>
                <td className="border-b border-zinc-800 px-4 py-3 text-zinc-400">{r.ugc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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
        <li><Link href="/answers/what-is-proof-based-content" className="hover:text-zinc-100">What is proof-based content? →</Link></li>
        <li><Link href="/compare/proofhook-vs-ugc-platform" className="hover:text-zinc-100">ProofHook vs. a UGC platform →</Link></li>
        <li><Link href="/how-it-works" className="hover:text-zinc-100">How it works →</Link></li>
        <li><Link href="/faq" className="hover:text-zinc-100">FAQ →</Link></li>
      </ul>

      <div className="mt-12">
        <CTA ctaId="answers-cta" label="Talk to ProofHook" subject="ProofHook — proof vs UGC" />
      </div>
    </MarketingShell>
  );
}
