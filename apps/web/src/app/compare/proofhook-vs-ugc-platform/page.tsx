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

const PAGE_URL = "/compare/proofhook-vs-ugc-platform";

export const metadata: Metadata = {
  title: "ProofHook vs. a UGC platform | ProofHook",
  description:
    "How ProofHook compares to a UGC creator-marketplace platform on scope, brief depth, hook quality, and search/AI authority work.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

const ROWS: { dimension: string; proofhook: string; ugc: string }[] = [
  {
    dimension: "Operating model",
    proofhook:
      "Studio-led production. We scope the brief, write the hooks, manage the production, run QA, and ship.",
    ugc:
      "Marketplace of creators. You write the brief, pick a creator, and review their cut.",
  },
  {
    dimension: "Brief depth",
    proofhook:
      "Structured intake — audience, goals, brand voice, offer, asset links, preferred start date — feeds directly into hook strategy.",
    ugc: "Creator-fillable brief; quality varies by who picks it up.",
  },
  {
    dimension: "Hook strategy",
    proofhook:
      "Multiple hooks per asset, angle variants, CTA alignment. Hook strategy is the engagement, not an afterthought.",
    ugc: "Creator chooses the hook; volume tends to dominate over angle quality.",
  },
  {
    dimension: "Turnaround",
    proofhook: "Fixed per-package: 7 days to 10–14 days.",
    ugc: "Highly variable; depends on creator availability.",
  },
  {
    dimension: "Search and AI authority",
    proofhook:
      "AI Search Authority Sprint covers structured data, entity pages, robots/sitemap, internal linking, Search Console / Webmaster Tools checklists.",
    ugc: "Out of scope for a UGC marketplace.",
  },
  {
    dimension: "Audit trail",
    proofhook:
      "Every step (payment, intake, production, QA, delivery, follow-up) is logged in the OS.",
    ugc: "Platform messaging + creator deliverables. Varies by platform.",
  },
];

export default function CompareUgcPlatformPage() {
  return (
    <MarketingShell
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "Compare", url: "/compare" },
        { label: "ProofHook vs. UGC platform", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />

      <header>
        <h1 className="text-3xl font-semibold tracking-tight">
          ProofHook vs. a UGC platform
        </h1>
        <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
          UGC creator marketplaces and ProofHook both produce short-form video.
          The shape of the work and the level of strategic load is different.
          Below is a side-by-side breakdown.
        </p>
      </header>

      <SectionHeading>Side-by-side</SectionHeading>
      <div className="mt-4 overflow-hidden rounded-lg border border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900 text-zinc-300">
            <tr>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">Dimension</th>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">ProofHook</th>
              <th className="border-b border-zinc-800 px-4 py-3 font-medium">UGC platform</th>
            </tr>
          </thead>
          <tbody className="text-zinc-300">
            {ROWS.map((r) => (
              <tr key={r.dimension} className="align-top">
                <td className="border-b border-zinc-800 px-4 py-3 font-medium text-zinc-100">
                  {r.dimension}
                </td>
                <td className="border-b border-zinc-800 px-4 py-3">{r.proofhook}</td>
                <td className="border-b border-zinc-800 px-4 py-3 text-zinc-400">{r.ugc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SectionHeading>When a UGC platform is the right call</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        If you need a high volume of low-cost talking-head clips and you have an
        in-house team to write briefs, pick creators, and quality-check
        deliverables, a UGC marketplace is the right tool. ProofHook is not.
      </p>

      <SectionHeading>When ProofHook is the right call</SectionHeading>
      <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
        If you need a tight number of paid-media-ready assets with hook strategy
        and offer alignment baked in, or you need search and AI authority work
        on the same operator surface, ProofHook is built for that. We are not a
        creator marketplace; we are a studio with an audit trail.
      </p>

      <div className="mt-12">
        <CTA label="Talk to ProofHook" subject="ProofHook — vs. UGC platform" />
      </div>
    </MarketingShell>
  );
}
