"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="body-theory"
      brandName="Body Theory"
      verticalOpener="Creative packages for fitness, supplement, recovery, and wellness brands that need more usable content and stronger campaign-ready assets."
      packageSlug="growth-content-pack"
      headline="A monthly content pack for fitness brands that need steady creative volume."
      subheadline="For brands that want recurring assets for social, campaigns, and product pushes without rebuilding the content process every week."
      price="Starting at $2,500/month"
      deliverables={["8 to 12 short-form assets per month", "Multiple hook and caption variations", "2 CTA angles", "Monthly creative refresh", "Structured delivery cadence"]}
      bestFit={["Growing supplement and fitness brands", "Recovery and wellness companies scaling content", "Brands with active social channels", "Teams that need consistent monthly output"]}
      outcome="You get a repeatable monthly stream of creative that helps you stay visible and gives you more to test."
      primaryCta="Start the Growth Pack"
      secondaryCta="Request package details"
      salesMicrocopy="Built for brands that need steady output, not random content bursts."
      hooks={[]}
    />
  );
}
