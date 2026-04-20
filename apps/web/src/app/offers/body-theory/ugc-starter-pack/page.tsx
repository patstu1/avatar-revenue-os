"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="body-theory"
      brandName="Body Theory"
      verticalOpener="Creative packages for fitness, supplement, recovery, and wellness brands that need more usable content and stronger campaign-ready assets."
      packageSlug="ugc-starter-pack"
      headline="Fast-turn fitness creative for brands that need more usable content now."
      subheadline="Designed for supplement, recovery, fitness, and wellness brands that need short-form assets, stronger hooks, and more content to work with right away."
      price="$1,500"
      deliverables={["4 short-form video assets", "3 hook variations", "1 CTA angle", "Light editing and packaging", "7-day turnaround"]}
      bestFit={["Supplement and recovery brands", "Fitness and wellness brands", "Founders who need fast proof-of-concept assets", "Brands entering short-form content for the first time"]}
      outcome="You leave with usable short-form creative you can post, test, and build from immediately."
      primaryCta="Get the Starter Pack"
      secondaryCta="See what's included"
      salesMicrocopy="Fastest way to get usable creative live."
      hooks={[]}
    />
  );
}
