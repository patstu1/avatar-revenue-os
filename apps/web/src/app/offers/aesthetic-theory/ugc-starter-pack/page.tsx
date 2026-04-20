"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="aesthetic-theory"
      brandName="Aesthetic Theory"
      verticalOpener="Creative packages for beauty, skincare, aesthetics, and wellness brands that need stronger short-form assets, sharper hooks, and better offer support."
      packageSlug="ugc-starter-pack"
      headline="Short-form beauty creative that makes your brand look current fast."
      subheadline="Built for skincare, beauty, aesthetics, and wellness brands that need fresh content, stronger hooks, and more usable assets without waiting on a full production cycle."
      price="$1,500"
      deliverables={["4 short-form video assets", "3 hook variations", "1 CTA angle", "Light editing and packaging", "7-day turnaround"]}
      bestFit={["Beauty and skincare brands", "Wellness and aesthetics brands", "Founders who need quick proof-of-concept assets", "Brands testing short-form creative for the first time"]}
      outcome="You leave with usable short-form creative you can post, test, and build from immediately."
      primaryCta="Get the Starter Pack"
      secondaryCta="See what's included"
      salesMicrocopy="Fastest way to get usable creative live."
      hooks={[]}
    />
  );
}
