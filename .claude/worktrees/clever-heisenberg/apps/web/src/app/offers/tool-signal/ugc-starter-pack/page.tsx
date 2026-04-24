"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="tool-signal"
      brandName="Tool Signal"
      verticalOpener="Creative packages for AI, SaaS, and software brands that need product-facing short-form content, stronger proof, and better top-of-funnel creative."
      packageSlug="ugc-starter-pack"
      headline="Fast-turn short-form content for software and AI brands that need proof fast."
      subheadline="A simple entry package for SaaS and AI companies that want more founder-style, product-facing, or explain-it-fast content without building an in-house production process first."
      price="$1,500"
      deliverables={["4 short-form video assets", "3 hook variations", "1 CTA angle", "Light editing and packaging", "7-day turnaround"]}
      bestFit={["SaaS and AI startups", "Developer tools and productivity brands", "Founders who need quick product-facing assets", "Software brands testing short-form creative"]}
      outcome="You leave with usable short-form creative you can post, test, and build from immediately."
      primaryCta="Get the Starter Pack"
      secondaryCta="See what's included"
      salesMicrocopy="Fastest way to get usable creative live."
      hooks={[]}
    />
  );
}
