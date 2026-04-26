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
  PackageCatalogOffersJsonLd,
  WebSiteJsonLd,
} from "@/components/jsonld";
import { PACKAGES, SITE_URL } from "@/lib/proofhook-packages";

const PAGE_URL = "/answers/how-much-do-short-form-content-packages-cost";

const FAQ = [
  {
    question: "Why publish prices?",
    answer:
      "Buyers waste hours on scoping calls when prices are hidden. Publishing prices filters in serious buyers and lets us spend our time on the work, not the qualification.",
  },
  {
    question: "Are there hidden fees?",
    answer:
      "No. The package price is the price. Add-ons (extra hooks, paid-media spend, additional industries) are quoted before you agree to them.",
  },
  {
    question: "How does this compare to a content agency?",
    answer:
      "Content agencies typically charge $5k–$25k+ per month for an open-ended retainer with custom scope. ProofHook publishes per-package pricing with fixed scope and turnaround.",
  },
];

export const metadata: Metadata = {
  title: "How much do short-form content packages cost? | ProofHook",
  description:
    "ProofHook universal packages: $1,500 (Signal Entry) to $7,500 (Creative Command). AI Search Authority Sprint from $4,500. Direct answer with the full price table.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function AnswerPricingPage() {
  return (
    <MarketingShell
      pageId="answers/how-much-do-short-form-content-packages-cost"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "Answers", url: "/answers" },
        { label: "Pricing", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <PackageCatalogOffersJsonLd />
      <FaqJsonLd qa={FAQ} />

      <header>
        <h1 className="text-3xl font-semibold leading-tight tracking-tight">
          How much do short-form content packages cost?
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-zinc-200 leading-relaxed">
          ProofHook&apos;s universal packages range from $1,500 (Signal Entry,
          7 days) to $7,500 (Creative Command, monthly). The AI Search
          Authority Sprint is from $4,500 over 10–14 days. Most other
          studio-and-agency options bundle creative into a $5k–$25k+ monthly
          retainer with custom scope.
        </p>
      </header>

      <SectionHeading>Full price table</SectionHeading>
      <div className="mt-4 overflow-hidden rounded-lg border border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900 text-zinc-300">
            <tr>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">Package</th>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">Price</th>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">Timeline</th>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">Best for</th>
            </tr>
          </thead>
          <tbody className="text-zinc-300">
            {PACKAGES.map((p) => (
              <tr key={p.slug} data-package={p.slug} className="align-top">
                <td className="border-b border-zinc-800 px-4 py-3 font-medium text-zinc-100">
                  {p.hasDetailPage ? (
                    <Link href={p.url} data-cta={`package-${p.slug}`} data-package={p.slug} className="hover:underline">
                      {p.name}
                    </Link>
                  ) : (
                    p.name
                  )}
                </td>
                <td className="border-b border-zinc-800 px-4 py-3 font-mono">
                  {p.priceFrom ? "From " : ""}${p.price.toLocaleString()}
                </td>
                <td className="border-b border-zinc-800 px-4 py-3">{p.timeline}</td>
                <td className="border-b border-zinc-800 px-4 py-3 text-zinc-400">{p.tagline}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SectionHeading>What the price covers</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Brief, hook strategy, production, QA, delivery, and a follow-up window.
        Each package is a fixed scope; what&apos;s in is published per package
        page. Add-ons are quoted before they&apos;re billed.
      </p>

      <SectionHeading>What we won&apos;t promise</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        We do not promise specific revenue, conversion, or click numbers tied
        to package output. We deliver paid-media-ready assets and a documented
        chain of custody. Performance depends on offer, audience, and channel.
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
        <li><Link href="/answers/best-content-package-for-founder-led-brands" className="hover:text-zinc-100">Which package fits a founder-led brand? →</Link></li>
        <li><Link href="/how-it-works" className="hover:text-zinc-100">How it works →</Link></li>
        <li><Link href="/compare/proofhook-vs-content-agency" className="hover:text-zinc-100">ProofHook vs. content agency →</Link></li>
        <li><Link href="/faq" className="hover:text-zinc-100">FAQ →</Link></li>
      </ul>

      <div className="mt-12">
        <CTA ctaId="answers-cta" label="Talk to ProofHook" subject="ProofHook — pricing" />
      </div>
    </MarketingShell>
  );
}
