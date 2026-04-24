"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="aesthetic-theory"
      brandName="Aesthetic Theory"
      verticalOpener="Creative packages for beauty, skincare, aesthetics, and wellness brands that need stronger short-form assets, sharper hooks, and better offer support."
      packageSlug="launch-sprint"
      headline="Fast-turn beauty creative for launches, pushes, and seasonal moments."
      subheadline="Built for promotions, launches, and urgent campaign windows when your brand needs strong creative quickly and cannot afford delay."
      price="Starting at $5,000"
      deliverables={["Fast-turn asset batch", "Launch-focused hook set", "CTA alignment", "Compressed delivery timeline", "Campaign-ready creative package"]}
      bestFit={["Product launches in beauty and skincare", "Seasonal promotion pushes", "Event or campaign windows", "Brands with urgent content demand"]}
      outcome="You get a concentrated batch of launch-ready creative fast enough to matter."
      primaryCta="Start a Launch Sprint"
      secondaryCta="Get launch support"
      salesMicrocopy="For urgent campaigns that need creative now, not next month."
      hooks={[]}
    />
  );
}
