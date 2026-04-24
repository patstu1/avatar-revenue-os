"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="body-theory"
      brandName="Body Theory"
      verticalOpener="Creative packages for fitness, supplement, recovery, and wellness brands that need more usable content and stronger campaign-ready assets."
      packageSlug="launch-sprint"
      headline="Fast-turn creative for supplement drops, campaign pushes, and fitness launches."
      subheadline="When timing matters, this sprint gives your brand a concentrated batch of campaign-ready creative built for immediate use."
      price="Starting at $5,000"
      deliverables={["Fast-turn asset batch", "Launch-focused hook set", "CTA alignment", "Compressed delivery timeline", "Campaign-ready creative package"]}
      bestFit={["Supplement drops and product launches", "Seasonal fitness campaign pushes", "Event or promotion windows", "Brands with urgent content demand"]}
      outcome="You get a concentrated batch of launch-ready creative fast enough to matter."
      primaryCta="Start a Launch Sprint"
      secondaryCta="Get launch support"
      salesMicrocopy="For urgent campaigns that need creative now, not next month."
      hooks={[]}
    />
  );
}
