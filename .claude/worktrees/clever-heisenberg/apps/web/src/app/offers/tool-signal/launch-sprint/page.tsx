"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="tool-signal"
      brandName="Tool Signal"
      verticalOpener="Creative packages for AI, SaaS, and software brands that need product-facing short-form content, stronger proof, and better top-of-funnel creative."
      packageSlug="launch-sprint"
      headline="Fast-turn launch creative for product pushes, feature launches, and campaign windows."
      subheadline="For SaaS and AI teams that need launch-ready short-form creative quickly enough to support a real release window."
      price="Starting at $5,000"
      deliverables={["Fast-turn asset batch", "Launch-focused hook set", "CTA alignment", "Compressed delivery timeline", "Campaign-ready creative package"]}
      bestFit={["Product and feature launches", "Funding announcements and pushes", "Seasonal or event campaigns", "Teams with urgent content demand"]}
      outcome="You get a concentrated batch of launch-ready creative fast enough to matter."
      primaryCta="Start a Launch Sprint"
      secondaryCta="Get launch support"
      salesMicrocopy="For urgent campaigns that need creative now, not next month."
      hooks={[]}
    />
  );
}
