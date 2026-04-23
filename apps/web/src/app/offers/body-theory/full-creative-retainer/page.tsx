"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="body-theory"
      brandName="Body Theory"
      verticalOpener="Creative packages for fitness, supplement, recovery, and wellness brands that need more usable content and stronger campaign-ready assets."
      packageSlug="full-creative-retainer"
      headline="A serious creative retainer for fitness and wellness brands that want more output."
      subheadline="For brands that need a consistent partner producing recurring content, stronger campaign assets, and a more reliable creative rhythm."
      price="Starting at $7,500/month"
      deliverables={["Recurring short-form creative production", "Multi-angle hook development", "Offer and landing support", "Reporting and strategy layer", "Priority turnaround", "Higher-volume monthly delivery"]}
      bestFit={["Funded fitness and supplement brands", "Aggressive growth teams", "Businesses with active ad spend", "Brands that need creative as an ongoing function"]}
      outcome="You get a more complete creative engine with stronger support, faster execution, and more strategic continuity."
      primaryCta="Book the Full Retainer"
      secondaryCta="Talk through your needs"
      salesMicrocopy="A deeper creative partnership for brands that need serious output."
      hooks={[]}
    />
  );
}
