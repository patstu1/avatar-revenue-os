"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="tool-signal"
      brandName="Tool Signal"
      verticalOpener="Creative packages for AI, SaaS, and software brands that need product-facing short-form content, stronger proof, and better top-of-funnel creative."
      packageSlug="full-creative-retainer"
      headline="A full creative retainer for AI and SaaS brands that need output at speed."
      subheadline="For teams that need recurring short-form content, stronger product-facing assets, faster execution, and a more complete creative support layer."
      price="Starting at $7,500/month"
      deliverables={["Recurring short-form creative production", "Multi-angle hook development", "Offer and landing support", "Reporting and strategy layer", "Priority turnaround", "Higher-volume monthly delivery"]}
      bestFit={["Funded SaaS and AI companies", "Aggressive growth teams in tech", "Businesses with active ad spend", "Brands that need creative as an ongoing operating function"]}
      outcome="You get a more complete creative engine with stronger support, faster execution, and more strategic continuity."
      primaryCta="Book the Full Retainer"
      secondaryCta="Talk through your needs"
      salesMicrocopy="A deeper creative partnership for brands that need serious output."
      hooks={[]}
    />
  );
}
