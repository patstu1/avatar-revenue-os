"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="aesthetic-theory"
      brandName="Aesthetic Theory"
      verticalOpener="Creative packages for beauty, skincare, aesthetics, and wellness brands that need stronger short-form assets, sharper hooks, and better offer support."
      packageSlug="full-creative-retainer"
      headline="A full creative partner for beauty brands that need serious output."
      subheadline="For beauty and aesthetics brands that want recurring production, stronger campaign support, and a more complete creative system behind their offers."
      price="Starting at $7,500/month"
      deliverables={["Recurring short-form creative production", "Multi-angle hook development", "Offer and landing support", "Reporting and strategy layer", "Priority turnaround", "Higher-volume monthly delivery"]}
      bestFit={["Funded beauty brands", "Aggressive growth teams in aesthetics", "Businesses with active ad spend", "Brands that need creative as an ongoing operating function"]}
      outcome="You get a more complete creative engine with stronger support, faster execution, and more strategic continuity."
      primaryCta="Book the Full Retainer"
      secondaryCta="Talk through your needs"
      salesMicrocopy="A deeper creative partnership for brands that need serious output."
      hooks={[]}
    />
  );
}
