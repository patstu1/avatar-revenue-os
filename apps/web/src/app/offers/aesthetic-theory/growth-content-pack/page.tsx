"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="aesthetic-theory"
      brandName="Aesthetic Theory"
      verticalOpener="Creative packages for beauty, skincare, aesthetics, and wellness brands that need stronger short-form assets, sharper hooks, and better offer support."
      packageSlug="growth-content-pack"
      headline="A monthly beauty content engine for brands that need more output and more consistency."
      subheadline="For brands that want recurring short-form creative, cleaner offer alignment, and a steadier stream of assets for social, paid, and campaign support."
      price="Starting at $2,500/month"
      deliverables={["8 to 12 short-form assets per month", "Multiple hook and caption variations", "2 CTA angles", "Monthly creative refresh", "Structured delivery cadence"]}
      bestFit={["Growing DTC beauty brands", "Aesthetic and skincare businesses scaling content", "Wellness brands that need monthly creative volume", "Brands with active social channels that need consistent output"]}
      outcome="You get a repeatable monthly stream of creative that helps you stay visible and gives you more to test."
      primaryCta="Start the Growth Pack"
      secondaryCta="Request package details"
      salesMicrocopy="Built for brands that need steady output, not random content bursts."
      hooks={[]}
    />
  );
}
