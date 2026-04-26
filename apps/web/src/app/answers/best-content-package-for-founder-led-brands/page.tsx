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
  WebSiteJsonLd,
} from "@/components/jsonld";
import { SITE_URL } from "@/lib/proofhook-packages";

const PAGE_URL = "/answers/best-content-package-for-founder-led-brands";

const FAQ = [
  {
    question: "Is there a 'cheapest' option that still works?",
    answer:
      "Signal Entry at $1,500 produces four short-form assets in seven days. It's not a discount; it's a deliberate scope for testing whether ProofHook's voice fits your brand.",
  },
  {
    question: "When should a founder-led brand use the AI Search Authority Sprint?",
    answer:
      "When your category is shifting faster than your site, when buyers are using AI tools to research your space, or when you're being mis-described by AI search systems and want to fix the inputs those systems read.",
  },
  {
    question: "Can I switch packages mid-engagement?",
    answer:
      "Yes — most founder-led brands start with Signal Entry to validate fit and roll into Momentum Engine or Paid Media Engine for sustained output.",
  },
];

export const metadata: Metadata = {
  title: "Best content package for founder-led brands | ProofHook",
  description:
    "It depends on stage. Signal Entry to test fit; Momentum Engine for volume; Conversion Architecture or Launch Sequence for repositioning. Direct answer with the decision tree.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function AnswerFounderLedPackagePage() {
  return (
    <MarketingShell
      pageId="answers/best-content-package-for-founder-led-brands"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "Answers", url: "/answers" },
        { label: "Best package for founder-led brands", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <PackageCatalogOffersJsonLd />
      <FaqJsonLd qa={FAQ} />

      <header>
        <h1 className="text-3xl font-semibold leading-tight tracking-tight">
          Best content package for founder-led brands
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-zinc-200 leading-relaxed">
          It depends on stage. Founder-led brands testing new positioning start
          with <Link href="/ai-search-authority" className="text-zinc-100 hover:underline">Signal Entry</Link>{" "}
          ($1,500, 7 days). Brands with an existing offer who need volume start
          with <strong>Momentum Engine</strong> ($2,500, monthly). Brands
          repositioning or relaunching start with <strong>Conversion Architecture</strong>{" "}
          ($3,500, 10–14 days) or <strong>Launch Sequence</strong> ($5,000, 10–14 days).
        </p>
      </header>

      <SectionHeading>Decision tree by stage</SectionHeading>

      <div className="mt-4 space-y-6 text-zinc-300 leading-relaxed">
        <div data-package="signal_entry">
          <p className="font-medium text-zinc-100">
            Stage: testing — &ldquo;does ProofHook&apos;s voice work for my brand?&rdquo;
          </p>
          <p className="mt-1.5 text-zinc-400">
            <strong>Signal Entry — $1,500, 7 days.</strong> Four short-form
            assets, one hook variant per asset. Lowest-friction way to validate
            fit before scaling spend.
          </p>
        </div>

        <div data-package="momentum_engine">
          <p className="font-medium text-zinc-100">
            Stage: scaling — &ldquo;the offer works; I need volume&rdquo;
          </p>
          <p className="mt-1.5 text-zinc-400">
            <strong>Momentum Engine — $2,500/mo.</strong> 8–12 short-form
            assets per month, multiple hook variants, two CTA angles, monthly
            refresh cadence.
          </p>
        </div>

        <div data-package="conversion_architecture">
          <p className="font-medium text-zinc-100">
            Stage: repositioning — &ldquo;the assets aren&apos;t landing&rdquo;
          </p>
          <p className="mt-1.5 text-zinc-400">
            <strong>Conversion Architecture — $3,500, 10–14 days.</strong>{" "}
            Audit your existing creative, rebuild hooks against the offer,
            deliver a roadmap.
          </p>
        </div>

        <div data-package="paid_media_engine">
          <p className="font-medium text-zinc-100">
            Stage: paid-media-led — &ldquo;Meta/TikTok ads are the channel&rdquo;
          </p>
          <p className="mt-1.5 text-zinc-400">
            <strong>Paid Media Engine — $4,500/mo.</strong> 12–20 short-form
            assets in month one, hook variations, offer/landing support,
            monthly optimization.
          </p>
        </div>

        <div data-package="launch_sequence">
          <p className="font-medium text-zinc-100">
            Stage: launching — &ldquo;I have a product/feature drop&rdquo;
          </p>
          <p className="mt-1.5 text-zinc-400">
            <strong>Launch Sequence — $5,000, 10–14 days.</strong> Launch-focused
            asset batch, launch-specific hook set, CTA alignment, compressed
            timeline.
          </p>
        </div>

        <div data-package="creative_command">
          <p className="font-medium text-zinc-100">
            Stage: high-throughput — &ldquo;I need a creative function, not a one-off&rdquo;
          </p>
          <p className="mt-1.5 text-zinc-400">
            <strong>Creative Command — $7,500/mo.</strong> Recurring creative
            production, multi-angle hooks, offer/landing support, priority
            turnaround.
          </p>
        </div>

        <div data-package="ai_search_authority_sprint">
          <p className="font-medium text-zinc-100">
            Stage: searchability — &ldquo;AI tools mis-describe my product&rdquo;
          </p>
          <p className="mt-1.5 text-zinc-400">
            <strong>AI Search Authority Sprint — from $4,500, 10–14 days.</strong>{" "}
            Fix the inputs search engines and AI search systems read about your
            brand. We do not promise rankings or AI placements.
          </p>
        </div>
      </div>

      <SectionHeading>What we won&apos;t promise</SectionHeading>
      <Bullets
        items={[
          "Specific revenue, conversion, or click numbers from any package",
          "Guaranteed Google rankings or AI Overview placement",
          "Guaranteed citations or recommendations in ChatGPT, Perplexity, or Bing Copilot",
        ]}
      />

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
        <li><Link href="/answers/how-much-do-short-form-content-packages-cost" className="hover:text-zinc-100">Pricing →</Link></li>
        <li><Link href="/how-it-works" className="hover:text-zinc-100">How it works →</Link></li>
        <li><Link href="/ai-search-authority" className="hover:text-zinc-100">AI Search Authority Sprint →</Link></li>
        <li><Link href="/faq" className="hover:text-zinc-100">FAQ →</Link></li>
      </ul>

      <div className="mt-12">
        <CTA ctaId="answers-cta" label="Talk to ProofHook" subject="ProofHook — founder-led brand fit" />
      </div>
    </MarketingShell>
  );
}
