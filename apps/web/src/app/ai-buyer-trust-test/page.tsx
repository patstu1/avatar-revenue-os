/**
 * Public AI Buyer Trust Test page.
 *
 * Server component: emits metadata + JSON-LD + the MarketingShell chrome
 * shared with every other ProofHook marketing surface (header, breadcrumb,
 * footer). The interactive quiz lives in quiz-client.tsx.
 *
 * Visual treatment (frosted cards, mint + powder blue, cinematic glow,
 * Bebas Neue headline) is scoped to this page — no other marketing page
 * is touched and no global theme tokens are added.
 */

import type { Metadata } from "next";
import { Bebas_Neue } from "next/font/google";

import { MarketingShell } from "@/components/marketing-shell";
import { OrganizationJsonLd, WebSiteJsonLd } from "@/components/jsonld";
import { SITE_URL } from "@/lib/proofhook-packages";

import { QuizClient } from "./quiz-client";

const bebas = Bebas_Neue({
  subsets: ["latin"],
  weight: "400",
  display: "swap",
});

const PAGE_URL = "/ai-buyer-trust-test";

export const metadata: Metadata = {
  title: "AI Buyer Trust Test — Free 3-minute diagnostic | ProofHook",
  description:
    "Take the AI Buyer Trust Test and see how easy your business is to find, trust, and choose. Free answer-based diagnostic in about 3 minutes.",
  alternates: { canonical: `${SITE_URL}${PAGE_URL}` },
  openGraph: {
    title: "AI Buyer Trust Test — ProofHook",
    description:
      "How easy is your business to find, trust, and choose? Take the free 3-minute AI Buyer Trust Test.",
    url: `${SITE_URL}${PAGE_URL}`,
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Buyer Trust Test — ProofHook",
    description:
      "How easy is your business to find, trust, and choose? Take the free 3-minute AI Buyer Trust Test.",
  },
};

export default function AiBuyerTrustTestPage() {
  return (
    <MarketingShell
      pageId="ai-buyer-trust-test"
      breadcrumbs={[
        { label: "Home", url: "/" },
        { label: "AI Buyer Trust Test", url: PAGE_URL },
      ]}
    >
      <OrganizationJsonLd />
      <WebSiteJsonLd />
      <QuizClient headlineFontClass={bebas.className} />
    </MarketingShell>
  );
}
