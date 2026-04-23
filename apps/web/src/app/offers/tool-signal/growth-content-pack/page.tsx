"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="tool-signal"
      brandName="Tool Signal"
      verticalOpener="Creative packages for AI, SaaS, and software brands that need product-facing short-form content, stronger proof, and better top-of-funnel creative."
      packageSlug="growth-content-pack"
      headline="A monthly content engine for SaaS brands that need more top-of-funnel assets."
      subheadline="For teams that want a steady stream of short-form content around product value, founder presence, use cases, and offer support."
      price="Starting at $2,500/month"
      deliverables={["8 to 12 short-form assets per month", "Multiple hook and caption variations", "2 CTA angles", "Monthly creative refresh", "Structured delivery cadence"]}
      bestFit={["Growing SaaS and AI companies", "Developer tools building audience", "Software brands with active social channels", "Teams that need consistent top-of-funnel content"]}
      outcome="You get a repeatable monthly stream of creative that helps you stay visible and gives you more to test."
      primaryCta="Start the Growth Pack"
      secondaryCta="Request package details"
      salesMicrocopy="Built for brands that need steady output, not random content bursts."
      hooks={[]}
    />
  );
}
