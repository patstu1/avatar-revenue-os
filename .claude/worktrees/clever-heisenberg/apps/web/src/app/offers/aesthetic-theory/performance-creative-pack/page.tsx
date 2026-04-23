"use client";

import PackagePage from "@/components/PackagePage";

export default function Page() {
  return (
    <PackagePage
      brandSlug="aesthetic-theory"
      brandName="Aesthetic Theory"
      verticalOpener="Creative packages for beauty, skincare, aesthetics, and wellness brands that need stronger short-form assets, sharper hooks, and better offer support."
      packageSlug="performance-creative-pack"
      headline="Beauty creative built to test, improve, and perform harder."
      subheadline="Made for brands that already understand creative affects conversion and want stronger hooks, more variations, and a more serious testing cadence."
      price="Starting at $4,500/month"
      deliverables={["12 to 20 short-form assets per month", "Hook and angle testing variations", "Offer and landing page support", "Monthly optimization pass", "Creative reporting and iteration recommendations"]}
      bestFit={["Beauty brands running paid traffic", "Teams with active offers or campaigns", "Brands that know creative quality affects results", "DTC brands ready to scale content volume"]}
      outcome="You get more creative, more testable variants, and a stronger performance-oriented content system."
      primaryCta="Apply for the Performance Pack"
      secondaryCta="View deliverables"
      salesMicrocopy="More variants, better hooks, stronger testing."
      hooks={[]}
    />
  );
}
