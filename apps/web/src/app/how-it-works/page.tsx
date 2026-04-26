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

const PAGE_URL = "/how-it-works";

export const metadata: Metadata = {
  title: "How ProofHook works | ProofHook",
  description:
    "How a ProofHook engagement runs end-to-end: scope, kickoff, intake, production, QA, delivery, and follow-up.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

const STEPS: { title: string; body: string }[] = [
  {
    title: "1. Scope & package selection",
    body: "You email hello@proofhook.com with the package you want and a short brief about your business. We reply with a scoping call slot, confirm fit, and lock the package.",
  },
  {
    title: "2. Checkout",
    body: "For the off-the-shelf packages (Signal Entry, Momentum Engine, Conversion Architecture, Paid Media Engine, Launch Sequence, Creative Command) you pay through a Stripe Payment Link. The AI Search Authority Sprint is scoped per engagement and quoted before checkout.",
  },
  {
    title: "3. Intake",
    body: "On payment, ProofHook automatically creates a Client record and emails you an intake form link. The form takes about 10 minutes — company, audience, goals, brand voice, asset links, preferred start date.",
  },
  {
    title: "4. Production",
    body: "Once intake is submitted, production starts. For creative packages: short-form assets per the package. For the AI Search Authority Sprint: audit, structured-data plan, page builds, internal linking map, Search Console / Webmaster Tools checklists.",
  },
  {
    title: "5. QA",
    body: "Every artifact runs through QA before it leaves us — a composite score across creative quality, brief alignment, and channel readiness for the creative packages, and a structural / schema check for the AI Search Authority Sprint.",
  },
  {
    title: "6. Delivery",
    body: "On QA pass we send the delivery email with the artifact link or the documentation pack. You confirm receipt; if anything needs adjustment, we iterate.",
  },
  {
    title: "7. Follow-up",
    body: "Seven days after delivery we follow up to gather signal on what landed, what didn't, and what to refresh — and to schedule the next engagement when one is appropriate.",
  },
];

export default function HowItWorksPage() {
  return (
    <MarketingShell
      breadcrumbs={[{ label: "Home", url: "/" }, { label: "How it works", url: PAGE_URL }]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />

      <header>
        <h1 className="text-3xl font-semibold tracking-tight">How ProofHook works</h1>
        <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
          A ProofHook engagement runs end-to-end on a single fulfillment chain —
          scope, checkout, intake, production, QA, delivery, follow-up. Every
          step is logged and operator-visible.
        </p>
      </header>

      <SectionHeading>The seven steps</SectionHeading>
      <ol className="mt-4 space-y-6">
        {STEPS.map((s) => (
          <li key={s.title}>
            <p className="font-medium text-zinc-100">{s.title}</p>
            <p className="mt-1.5 text-zinc-400 leading-relaxed">{s.body}</p>
          </li>
        ))}
      </ol>

      <SectionHeading>What ProofHook commits to</SectionHeading>
      <Bullets
        items={[
          "Stated turnaround per package",
          "QA pass before delivery — no half-finished artifacts",
          "A real intake; no generic deliverable without buyer context",
          "Operator-visible audit trail from payment to follow-up",
          "No fake reviews, no fake citations, no fake placement claims",
        ]}
      />

      <SectionHeading>What ProofHook does not commit to</SectionHeading>
      <Bullets
        items={[
          "Guaranteed Google rankings",
          "Guaranteed citations or recommendations in ChatGPT, Perplexity, Bing Copilot, or AI Overviews",
          "Specific revenue or conversion numbers tied to creative output",
          "Free re-scoping when the underlying brief changes",
        ]}
      />

      <SectionHeading>Related</SectionHeading>
      <ul className="mt-4 grid gap-2 text-zinc-300 sm:grid-cols-2">
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
        <li>
          <Link href="/compare/proofhook-vs-content-agency" className="hover:text-zinc-100">
            ProofHook vs. a content agency →
          </Link>
        </li>
      </ul>

      <div className="mt-12">
        <CTA label="Start an engagement" subject="ProofHook — start engagement" />
      </div>
    </MarketingShell>
  );
}
