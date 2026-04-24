"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="tool-signal"
      brandName="Tool Signal"
      verticalOpener="Creative packages for AI, SaaS, and software brands that need product-facing short-form content, stronger proof, and better top-of-funnel creative."
      packageSlug="creative-strategy-funnel-upgrade"
      headline="Strengthen the message, the offer, and the path from content to conversion."
      subheadline="Ideal for SaaS and AI brands that have product activity but need better content positioning, sharper messaging, and a cleaner conversion path."
      price="Starting at $2,500"
      deliverables={["Messaging refinement", "Offer positioning review", "Landing page or funnel upgrade recommendations", "Content-to-CTA alignment", "Strategic improvement plan"]}
      bestFit={["SaaS brands with product activity but weak positioning", "Teams with scattered messaging", "Clients who need a cleaner conversion path"]}
      outcome="You leave with a clearer message, a stronger offer path, and a better conversion foundation."
      primaryCta="Upgrade the Funnel"
      secondaryCta="See how it works"
      salesMicrocopy="Make the content and the conversion path work together."
      hooks={[]}
    />
  );
}
