"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="tool-signal"
      brandName="Tool Signal"
      verticalOpener="Creative packages for AI, SaaS, and software brands that need product-facing short-form content, stronger proof, and better top-of-funnel creative."
      packageSlug="performance-creative-pack"
      headline="Performance creative for SaaS brands that want more testable content and sharper hooks."
      subheadline="Built for teams running campaigns, launches, or active acquisition who need stronger creative angles, more variants, and better alignment between content and offer."
      price="Starting at $4,500/month"
      deliverables={["12 to 20 short-form assets per month", "Hook and angle testing variations", "Offer and landing page support", "Monthly optimization pass", "Creative reporting and iteration recommendations"]}
      bestFit={["SaaS brands running paid acquisition", "AI companies with active campaigns", "Teams that need creative testing at scale", "Software brands with active ad spend"]}
      outcome="You get more creative, more testable variants, and a stronger performance-oriented content system."
      primaryCta="Apply for the Performance Pack"
      secondaryCta="View deliverables"
      salesMicrocopy="More variants, better hooks, stronger testing."
      hooks={[]}
    />
  );
}
