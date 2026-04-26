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

const PAGE_URL = "/answers/what-is-proof-based-content";

const FAQ = [
  {
    question: "Is proof-based content the same as UGC?",
    answer:
      "No. UGC is creator-led, marketplace-driven, and usually unpolished. Proof-based content is studio-led, brief-driven, and built around verifiable claims and hook strategy.",
  },
  {
    question: "Does proof-based content guarantee performance?",
    answer:
      "No. We do not guarantee click-through, conversion, or revenue numbers. Proof-based content gives you assets that lead with verifiable claims; how those claims perform in your funnel is decided by your offer, audience, and channel.",
  },
  {
    question: "What's in a proof-based content asset?",
    answer:
      "A hook anchored on a verifiable claim, a body that demonstrates that claim, and a CTA aligned with the offer. Multiple hook variants per asset on most packages.",
  },
];

export const metadata: Metadata = {
  title: "What is proof-based content? | ProofHook",
  description:
    "Proof-based content is studio-led short-form video that leads with verifiable claims rather than opinion or vibe. Direct answer in three sentences.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function AnswerWhatIsProofContentPage() {
  return (
    <MarketingShell
      pageId="answers/what-is-proof-based-content"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "Answers", url: "/answers" },
        { label: "What is proof-based content?", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <FaqJsonLd qa={FAQ} />

      <header>
        <h1 className="text-3xl font-semibold leading-tight tracking-tight">
          What is proof-based content?
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-zinc-200 leading-relaxed">
          Proof-based content is short-form video creative that leads with
          verifiable claims — real numbers, real product behavior, real evidence
          — rather than opinion or vibe. It&apos;s the operating model behind
          ProofHook&apos;s packages: every asset has to clear a quality bar
          before it ships, and every hook has to be anchored on something the
          buyer can check.
        </p>
      </header>

      <SectionHeading>Why it&apos;s a different category</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Most short-form creative on paid feeds today is opinion-driven —
        creator vibes, lifestyle b-roll, hook-then-pitch. That works when the
        category is trust-light. When the buyer is paying $1,500–$50k or making
        a B2B purchase, opinion isn&apos;t enough. Proof-based content earns
        attention by giving the buyer something to check, not something to
        feel.
      </p>

      <SectionHeading>What it looks like in practice</SectionHeading>
      <Bullets
        items={[
          "Hook anchored on a verifiable claim, not on a personality",
          "Body that demonstrates the claim — screenshot, dataset, before/after, on-product",
          "CTA aligned with the offer, not a generic 'check the link in bio'",
          "Multiple hook variants per asset so paid spend can find what lands",
          "QA pass before ship — no half-finished assets",
        ]}
      />

      <SectionHeading>How ProofHook delivers it</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Through universal creative packages: Signal Entry, Momentum Engine,
        Conversion Architecture, Paid Media Engine, Launch Sequence, and
        Creative Command. Each one is a fixed-scope engagement with published
        pricing and a documented intake-to-delivery chain.{" "}
        <Link href="/how-it-works" className="text-zinc-100 hover:underline">
          See how it works →
        </Link>
      </p>

      <SectionHeading>What we won&apos;t promise</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        We do not guarantee click-through, conversion, or revenue numbers. We
        ship paid-media-ready proof-based assets. Performance depends on your
        offer, audience, and channel — and you should be skeptical of any
        creative shop that promises otherwise.
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
        <li>
          <Link href="/answers/proof-content-vs-ugc" className="hover:text-zinc-100">
            Proof-based content vs. UGC →
          </Link>
        </li>
        <li>
          <Link href="/how-it-works" className="hover:text-zinc-100">
            How it works →
          </Link>
        </li>
        <li>
          <Link href="/ai-search-authority" className="hover:text-zinc-100">
            AI Search Authority Sprint →
          </Link>
        </li>
        <li>
          <Link href="/faq" className="hover:text-zinc-100">
            FAQ →
          </Link>
        </li>
      </ul>

      <div className="mt-12">
        <CTA
          ctaId="answers-cta"
          label="Talk to ProofHook"
          subject="ProofHook — proof-based content"
        />
      </div>
    </MarketingShell>
  );
}
