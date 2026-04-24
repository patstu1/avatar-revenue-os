"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="aesthetic-theory"
      brandName="Aesthetic Theory"
      verticalOpener="Creative packages for beauty, skincare, aesthetics, and wellness brands that need stronger short-form assets, sharper hooks, and better offer support."
      packageSlug="creative-strategy-funnel-upgrade"
      headline="Tighten the message, sharpen the offer, and improve the conversion path."
      subheadline="For brands with decent traffic or content activity that still need the offer, messaging, and landing path to work together more cleanly."
      price="Starting at $2,500"
      deliverables={["Messaging refinement", "Offer positioning review", "Landing page or funnel upgrade recommendations", "Content-to-CTA alignment", "Strategic improvement plan"]}
      bestFit={["Brands with traffic but weak conversion", "Teams with scattered messaging", "Clients already buying content who need stronger downstream performance"]}
      outcome="You leave with a clearer message, a stronger offer path, and a better conversion foundation."
      primaryCta="Upgrade the Funnel"
      secondaryCta="See how it works"
      salesMicrocopy="Make the content and the conversion path work together."
      hooks={[]}
    />
  );
}
