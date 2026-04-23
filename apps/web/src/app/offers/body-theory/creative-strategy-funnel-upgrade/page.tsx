"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="body-theory"
      brandName="Body Theory"
      verticalOpener="Creative packages for fitness, supplement, recovery, and wellness brands that need more usable content and stronger campaign-ready assets."
      packageSlug="creative-strategy-funnel-upgrade"
      headline="Make your content, offer, and conversion path actually work together."
      subheadline="Best for fitness and wellness brands with active campaigns that need cleaner messaging, stronger offer positioning, and a better content-to-conversion path."
      price="Starting at $2,500"
      deliverables={["Messaging refinement", "Offer positioning review", "Landing page or funnel upgrade recommendations", "Content-to-CTA alignment", "Strategic improvement plan"]}
      bestFit={["Fitness brands with traffic but weak conversion", "Teams with scattered messaging", "Clients who need stronger downstream performance"]}
      outcome="You leave with a clearer message, a stronger offer path, and a better conversion foundation."
      primaryCta="Upgrade the Funnel"
      secondaryCta="See how it works"
      salesMicrocopy="Make the content and the conversion path work together."
      hooks={[]}
    />
  );
}
