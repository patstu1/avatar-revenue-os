"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="body-theory"
      brandName="Body Theory"
      verticalOpener="Creative packages for fitness, supplement, recovery, and wellness brands that need more usable content and stronger campaign-ready assets."
      packageSlug="performance-creative-pack"
      headline="Performance-focused fitness creative with more hooks, more variants, and more testing room."
      subheadline="For brands running offers or paid traffic that need stronger creative angles, better testing coverage, and more useful output each month."
      price="Starting at $4,500/month"
      deliverables={["12 to 20 short-form assets per month", "Hook and angle testing variations", "Offer and landing page support", "Monthly optimization pass", "Creative reporting and iteration recommendations"]}
      bestFit={["Fitness brands running paid traffic", "Supplement brands with active campaigns", "Brands that already know creative quality affects results", "Teams ready to scale creative testing"]}
      outcome="You get more creative, more testable variants, and a stronger performance-oriented content system."
      primaryCta="Apply for the Performance Pack"
      secondaryCta="View deliverables"
      salesMicrocopy="More variants, better hooks, stronger testing."
      hooks={[]}
    />
  );
}
