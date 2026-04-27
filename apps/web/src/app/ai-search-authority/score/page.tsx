import type { Metadata } from "next";

import { AiBuyerTrustTest } from "@/components/ai-buyer-trust/Test";
import {
  WhatProofHookChecksSection,
  WhatTheScoreRevealsSection,
} from "@/components/ai-buyer-trust/DecisionLayerSections";
import { MarketingShell } from "@/components/marketing-shell";
import {
  OrganizationJsonLd,
  WebSiteJsonLd,
} from "@/components/jsonld";
import { SITE_URL } from "@/lib/proofhook-packages";

const PAGE_URL = "/ai-search-authority/score";

export const metadata: Metadata = {
  title: "AI Buyer Trust Test — ProofHook",
  description:
    "Take the AI Buyer Trust Test. Based on public website signals: offers, proof, FAQs, schema, comparisons, crawlability, and trust structure.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
};

export default function AiSearchAuthorityScorePage() {
  return (
    <MarketingShell
      pageId="ai-search-authority-score"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "AI Buyer Trust", url: "/ai-search-authority" },
        { label: "Test", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />

      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-zinc-500">
          AI Buyer Trust Infrastructure
        </p>
        <h1 className="mt-3 text-3xl font-semibold leading-tight tracking-tight text-zinc-100 sm:text-4xl">
          Check your AI Buyer Trust Score
        </h1>
        <p className="mt-4 max-w-2xl text-zinc-200 leading-relaxed">
          Google helped customers find businesses.
          <br />
          AI is helping them decide who to trust.
        </p>
        <p className="mt-3 max-w-2xl text-zinc-300 leading-relaxed">
          A new era of search is here — and it is bigger than Google.
          See how clearly your business is structured for the AI decision
          layer.
        </p>
        <p className="mt-3 max-w-2xl text-sm text-zinc-400 leading-relaxed">
          Based on public website signals: offers, proof, FAQs, schema,
          comparisons, crawlability, and trust structure.
        </p>
      </header>

      <div className="mt-10">
        <AiBuyerTrustTest />
      </div>

      <WhatProofHookChecksSection />
      <WhatTheScoreRevealsSection />
    </MarketingShell>
  );
}
