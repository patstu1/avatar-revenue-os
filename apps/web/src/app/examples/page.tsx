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

const PAGE_URL = "/examples";

const FAQ = [
  {
    question: "Are these real customer assets?",
    answer:
      "These are deliverable-structure examples — what a pack contains, not who bought it. We share real customer references and representative work in a scoping call, not on a public examples page.",
  },
  {
    question: "Can I download an example asset?",
    answer:
      "Sample structures are downloadable on request via hello@proofhook.com. We don't publish raw customer assets on the marketing surface.",
  },
  {
    question: "Why no public testimonials?",
    answer:
      "Most operator-specific deal terms are confidential. We share work with prospective buyers; we don't run a testimonial wall.",
  },
];

export const metadata: Metadata = {
  title: "Examples — sample deliverable structures | ProofHook",
  description:
    "Sample deliverable structures for each ProofHook package. Honest scaffolding, no invented customers, no fabricated metrics.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function ExamplesPage() {
  return (
    <MarketingShell
      pageId="examples"
      breadcrumbs={[{ label: "Home", url: "/" }, { label: "Examples", url: PAGE_URL }]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <FaqJsonLd qa={FAQ} />

      <header>
        <h1 className="text-3xl font-semibold leading-tight tracking-tight">
          Examples — sample deliverable structures
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-zinc-200 leading-relaxed">
          The shape of what each ProofHook package ships. No invented
          customers, no fake metrics — these are scaffolds you can map to your
          own business. Real customer assets and references are shared in a
          scoping call, not on a public examples page.
        </p>
      </header>

      <SectionHeading>Example: Signal Entry pack ($1,500, 7 days)</SectionHeading>
      <Bullets
        items={[
          "Asset 01 — hook anchored on a verifiable claim (e.g. 'X reduced onboarding from 14 days to 3'); body demonstrates the claim; CTA to the offer",
          "Asset 02 — angle variant on the same claim, different opening frame",
          "Asset 03 — counter-objection variant ('isn't this just a $99 tool?')",
          "Asset 04 — outcome variant (what the buyer's life looks like after)",
          "Hook strategy memo — what each hook is testing, why",
          "Delivery email with the pack link",
        ]}
      />

      <SectionHeading>Example: Momentum Engine month-one pack ($2,500/mo)</SectionHeading>
      <Bullets
        items={[
          "8–12 short-form video assets",
          "Multiple hook variants per asset",
          "2 CTA angles tested across the pack",
          "Monthly refresh — recurring engagement, new pack each month",
          "Hook performance review at month boundaries",
        ]}
      />

      <SectionHeading>Example: AI Search Authority Sprint pack (from $4,500, 10–14 days)</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Documentation + implementation pack delivered as a single archive,
        ready to ship to your dev team or for ProofHook to push directly:
      </p>
      <Bullets
        items={[
          "AI search and entity audit (PDF/MD) — current state, gaps, prioritized fix list",
          "robots.txt diff with line-by-line rationale",
          "sitemap.xml proposal listing every public marketing surface",
          "JSON-LD blocks: Organization, WebSite, Service, Product/Offer (per package), FAQPage, BreadcrumbList",
          "About / entity page draft",
          "FAQ page draft with FAQPage JSON-LD",
          "How-it-works page draft",
          "2 industry context page drafts",
          "2 comparison page drafts",
          "5 answer-engine content page drafts",
          "Internal linking map (graph + recommendations)",
          "Google Search Console + Bing Webmaster Tools setup checklists",
          "AI referral tracking plan",
          "External citation / backlink target checklist",
        ]}
      />

      <SectionHeading>What we won&apos;t put on this page</SectionHeading>
      <Bullets
        items={[
          "Customer logos we don't have written permission to publish",
          "Before/after metrics we can't attribute to our work",
          "AI-generated reviews or testimonials",
          "Screenshots of dashboards we don't have data for",
          "Implied or explicit ranking / AI-citation guarantees",
        ]}
      />

      <SectionHeading>Want a real example?</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Email{" "}
        <a href="mailto:hello@proofhook.com" className="text-zinc-100 hover:underline">
          hello@proofhook.com
        </a>{" "}
        with the package you&apos;re scoping. We&apos;ll share representative
        recent work with comparable shape on a scoping call. No public roster,
        no fabricated proof.
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
        <li><Link href="/proof" className="hover:text-zinc-100">Proof — workflow + audit trail →</Link></li>
        <li><Link href="/how-it-works" className="hover:text-zinc-100">How it works →</Link></li>
        <li><Link href="/ai-search-authority" className="hover:text-zinc-100">AI Search Authority Sprint →</Link></li>
        <li><Link href="/faq" className="hover:text-zinc-100">FAQ →</Link></li>
      </ul>

      <div className="mt-12">
        <CTA ctaId="examples-cta" label="Request a representative example" subject="ProofHook — example walkthrough" />
      </div>
    </MarketingShell>
  );
}
