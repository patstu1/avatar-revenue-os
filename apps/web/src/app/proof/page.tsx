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

const PAGE_URL = "/proof";

const FAQ = [
  {
    question: "Why don't you publish customer names and case-study numbers?",
    answer:
      "Most operator-specific deal terms are confidential. We share work and references with prospective buyers in a relevant fit on request, but we don't publish a public client roster or fabricate metrics. If you want to verify, ask hello@proofhook.com for a portfolio walkthrough.",
  },
  {
    question: "Can I see what a content pack contains before I buy?",
    answer:
      "Yes. The structure of every package is published on its detail surface, and we'll share representative deliverable examples with prospective buyers in a scoping call.",
  },
  {
    question: "How do I verify that production actually ran?",
    answer:
      "Every engagement leaves an audit trail: payment, intake, production_job, QA review, delivery. The operator surface logs each transition. You see the deliverable; we see the chain of custody behind it.",
  },
];

export const metadata: Metadata = {
  title: "Proof — what ProofHook actually ships | ProofHook",
  description:
    "Honest proof: deliverable structure, workflow, and what each ProofHook package contains. No invented testimonials, no fabricated case studies, no fake AI placement claims.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function ProofPage() {
  return (
    <MarketingShell
      pageId="proof"
      breadcrumbs={[{ label: "Home", url: "/" }, { label: "Proof", url: PAGE_URL }]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <FaqJsonLd qa={FAQ} />

      <header>
        <h1 className="text-3xl font-semibold leading-tight tracking-tight">
          Proof — what ProofHook actually ships
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-zinc-200 leading-relaxed">
          Most agencies&apos; &ldquo;proof&rdquo; pages are testimonial walls.
          Ours is a description of the deliverable structure, the workflow, and
          the audit trail. We don&apos;t publish customer logos we can&apos;t
          back up, fabricate metrics, or invent case studies.
        </p>
      </header>

      <SectionHeading>What a content pack contains</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Every creative-package deliverable (Signal Entry, Momentum Engine,
        Conversion Architecture, Paid Media Engine, Launch Sequence, Creative
        Command) is shipped as a structured pack:
      </p>
      <Bullets
        items={[
          "Edited short-form video assets at the count specified in the package",
          "Multiple hook variants per asset (count varies per package)",
          "Hook strategy memo: which claim each hook is anchored on, why, what to test against",
          "Offer/CTA alignment notes per asset — what the buyer should do next, why this CTA",
          "Source media + project files where applicable, so revisions don't require re-shooting",
          "Delivery email with the pack link and a follow-up window scheduled",
        ]}
      />

      <SectionHeading>What an AI Search Authority Sprint contains</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        The AI Search Authority Sprint deliverable is a documentation and
        implementation pack:
      </p>
      <Bullets
        items={[
          "AI search and entity audit — current state, gaps, prioritized fix list",
          "robots.txt and crawler access review with recommended changes",
          "sitemap.xml and canonical URL review",
          "Structured-data implementation plan + assets: Organization, WebSite, Service, Product/Offer, FAQPage, BreadcrumbList JSON-LD",
          "About / entity page draft",
          "FAQ page draft",
          "How-it-works page draft",
          "2 industry / vertical context pages",
          "2 comparison pages",
          "5 answer-engine content pages targeting buyer-intent queries",
          "Internal linking map",
          "Google Search Console + Bing Webmaster Tools setup checklists",
          "AI referral tracking plan",
          "External citation / backlink target checklist (the outreach is the buyer's part)",
        ]}
      />

      <SectionHeading>Workflow proof — chain of custody</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Every engagement runs on the same audit-traced fulfillment chain. Every
        transition writes an event to the operator surface, so &ldquo;did the
        work happen?&rdquo; is a queryable question, not a trust exercise:
      </p>
      <Bullets
        items={[
          "Payment confirmed — Stripe webhook, signed and verified",
          "Client created — first paying buyer of this email gets a Client record",
          "Intake sent — SendGrid invite with a token-gated form",
          "Intake submitted — structured responses captured",
          "Project + brief created — cascade fires on intake completion",
          "Production job queued + picked up — beat-driven worker advancement",
          "Artifact generated — content_pack output URL or sprint documentation pack",
          "QA passed — composite quality score against threshold",
          "Delivery sent — email to the buyer with the pack link",
          "Follow-up scheduled — auto-dispatched at the configured interval",
        ]}
      />
      <p className="mt-4 max-w-2xl text-sm text-zinc-400 leading-relaxed">
        Every step above corresponds to a row in the OS — a real entry the
        operator can read and you can audit on request. No phantom production.
      </p>

      <SectionHeading>What we won&apos;t do</SectionHeading>
      <Bullets
        items={[
          "Publish customer names without their permission",
          "Fabricate metrics or invent case studies",
          "Show before/after numbers we can't attribute to our work",
          "Promise rankings, AI placements, citations, or specific revenue",
          "Use AI-generated 'testimonials' or fake reviews",
        ]}
      />

      <SectionHeading>Want to see real work?</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        Email{" "}
        <a href="mailto:hello@proofhook.com" className="text-zinc-100 hover:underline">
          hello@proofhook.com
        </a>{" "}
        with a short note about your business and which package you&apos;re
        considering. We&apos;ll share representative deliverables relevant to
        your fit on a scoping call. No public roster — but we don&apos;t hide
        the work, either.
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
        <li><Link href="/examples" className="hover:text-zinc-100">Examples →</Link></li>
        <li><Link href="/how-it-works" className="hover:text-zinc-100">How it works →</Link></li>
        <li><Link href="/ai-search-authority" className="hover:text-zinc-100">AI Search Authority Sprint →</Link></li>
        <li><Link href="/faq" className="hover:text-zinc-100">FAQ →</Link></li>
      </ul>

      <div className="mt-12">
        <CTA ctaId="proof-cta" label="Request a portfolio walkthrough" subject="ProofHook — portfolio walkthrough" />
      </div>
    </MarketingShell>
  );
}
