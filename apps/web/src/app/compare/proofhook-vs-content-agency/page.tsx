import type { Metadata } from "next";

import {
  CTA,
  MarketingShell,
  SectionHeading,
} from "@/components/marketing-shell";
import {
  OrganizationJsonLd,
  WebSiteJsonLd,
} from "@/components/jsonld";
import { SITE_URL } from "@/lib/proofhook-packages";

const PAGE_URL = "/compare/proofhook-vs-content-agency";

export const metadata: Metadata = {
  title: "ProofHook vs. a content agency | ProofHook",
  description:
    "How ProofHook compares to a traditional content agency on scope, turnaround, transparency, and AI/search authority deliverables.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

const ROWS: { dimension: string; proofhook: string; agency: string }[] = [
  {
    dimension: "Scope per engagement",
    proofhook:
      "Fixed-package short-form creative or a 10–14 day AI Search Authority Sprint with explicit deliverables.",
    agency:
      "Open-ended retainer covering brand, content, and campaigns — scope and deliverables negotiated per quarter.",
  },
  {
    dimension: "Turnaround",
    proofhook: "7 days (Signal Entry) to 10–14 days (most other packages).",
    agency: "Two to six weeks for first creative; longer for site or schema work.",
  },
  {
    dimension: "Pricing model",
    proofhook: "Published per-package pricing. AI Search Authority Sprint from $4,500.",
    agency: "Custom quote per client; typically $5k–$25k+ per month.",
  },
  {
    dimension: "Audit trail",
    proofhook:
      "Every step from payment to follow-up is logged in the OS — operator-visible payment, intake, production job, QA, delivery, follow-up.",
    agency: "Project-management tool plus email; varies by agency.",
  },
  {
    dimension: "Search and AI authority work",
    proofhook:
      "AI Search Authority Sprint: structured data, entity pages, robots/sitemap, internal linking map, Search Console / Webmaster Tools checklists, AI referral tracking plan.",
    agency:
      "Often handled by a separate SEO retainer or sub-contractor; rarely includes JSON-LD across Organization / WebSite / Service / Product / FAQPage / BreadcrumbList in 10–14 days.",
  },
  {
    dimension: "Promises",
    proofhook:
      "We do not promise rankings, AI placements, or citations. We improve the inputs those systems use.",
    agency:
      "Some agencies promise rankings or growth numbers. Some don't. Read the contract carefully.",
  },
];

export default function CompareContentAgencyPage() {
  return (
    <MarketingShell
      pageId="compare/proofhook-vs-content-agency"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "Compare", url: "/compare" },
        { label: "ProofHook vs. content agency", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />

      <header>
        <h1 className="text-3xl font-semibold tracking-tight">
          ProofHook vs. a content agency
        </h1>
        <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
          Both produce creative; the operating model is different. Below is an
          honest, dimension-by-dimension comparison so you can pick the right
          shape of partner — not a sales pitch.
        </p>
      </header>

      <SectionHeading>Side-by-side</SectionHeading>
      <div className="mt-4 overflow-hidden rounded-lg border border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900 text-zinc-300">
            <tr>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">Dimension</th>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">ProofHook</th>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">Content agency</th>
            </tr>
          </thead>
          <tbody className="text-zinc-300">
            {ROWS.map((r) => (
              <tr key={r.dimension} className="align-top">
                <td className="border-b border-zinc-800 px-4 py-3 font-medium text-zinc-100">
                  {r.dimension}
                </td>
                <td className="border-b border-zinc-800 px-4 py-3">{r.proofhook}</td>
                <td className="border-b border-zinc-800 px-4 py-3 text-zinc-400">
                  {r.agency}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SectionHeading>When a content agency is the right call</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        If you need full-stack brand work — strategy, identity, long-form
        editorial, paid media buying, social management, PR — under one roof on
        a quarterly retainer, an established content agency is a better fit than
        ProofHook. We deliberately stay narrow.
      </p>

      <SectionHeading>When ProofHook is the right call</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        If you need short-form creative on a tight turnaround with a clear
        deliverable, or you need your site and brand to be easier for search
        engines and AI systems to understand and cite — and you want a
        published price and a documented chain of custody — ProofHook is built
        for that.
      </p>

      <div className="mt-12">
        <CTA
          label="Talk to ProofHook"
          subject="ProofHook — vs. content agency"
        />
      </div>
    </MarketingShell>
  );
}
