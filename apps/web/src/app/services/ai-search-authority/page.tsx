import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { SITE_URL } from "@/lib/proofhook-packages";

const CANONICAL = `${SITE_URL}/ai-search-authority`;

export const metadata: Metadata = {
  title: "AI Search Authority Sprint | ProofHook",
  description:
    "AI Search Authority Sprint: improve machine readability, strengthen entity authority, and increase eligibility for search and AI discovery.",
  alternates: { canonical: CANONICAL },
};

export default function ServicesAiSearchAuthorityRedirect() {
  // /services/ai-search-authority is a sibling URL listed in the spec.
  // Both this and /ai-search-authority must resolve. We canonical-redirect
  // here so crawlers consolidate signal on a single URL while both paths
  // remain valid entry points for buyers and link-builders.
  redirect("/ai-search-authority");
}
